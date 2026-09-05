from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nanoni.domain.enums import JobStatus
from nanoni.domain.models import Job
from nanoni.domain.transitions import ensure_transition


def enqueue(
    db: Session,
    *,
    job_type: str,
    payload: dict,
    idempotency_key: str | None = None,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> Job:
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
        if existing:
            return existing
    job = Job(
        type=job_type,
        payload=payload,
        idempotency_key=idempotency_key,
        run_after=run_after or datetime.now(UTC),
        max_attempts=max_attempts,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.scalar(select(Job).where(Job.idempotency_key == idempotency_key))
            if existing:
                return existing
        raise
    return job


def claim_next(db: Session, worker_id: str, *, now: datetime | None = None) -> Job | None:
    now = now or datetime.now(UTC)
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED, Job.run_after <= now)
        .order_by(Job.run_after, Job.created_at)
        .limit(1)
    )
    job = db.scalar(stmt)
    if not job:
        return None
    ensure_transition(JobStatus, job.status, JobStatus.RUNNING)
    job.status = JobStatus.RUNNING
    job.locked_at = now
    job.lock_owner = worker_id
    job.attempts += 1
    db.add(job)
    db.flush()
    return job


def recover_stale(
    db: Session,
    *,
    now: datetime | None = None,
    stale_after: timedelta = timedelta(minutes=15),
) -> int:
    now = now or datetime.now(UTC)
    jobs = list(
        db.scalars(
            select(Job).where(
                Job.status == JobStatus.RUNNING,
                Job.locked_at.is_not(None),
                Job.locked_at <= now - stale_after,
            )
        )
    )
    for job in jobs:
        job.status = JobStatus.QUEUED
        job.run_after = now
        job.locked_at = None
        job.lock_owner = None
        job.last_error = "recovered stale worker lock"
        db.add(job)
    if jobs:
        db.flush()
    return len(jobs)


def succeed(db: Session, job: Job) -> None:
    ensure_transition(JobStatus, job.status, JobStatus.SUCCEEDED)
    job.status = JobStatus.SUCCEEDED
    job.locked_at = None
    job.lock_owner = None
    db.add(job)


def fail(db: Session, job: Job, error: str, *, retry_delay_seconds: int = 30) -> None:
    if job.attempts < job.max_attempts:
        ensure_transition(JobStatus, job.status, JobStatus.FAILED_RETRYABLE)
        job.status = JobStatus.FAILED_RETRYABLE
        job.last_error = error
        db.add(job)
        db.flush()
        ensure_transition(JobStatus, job.status, JobStatus.QUEUED)
        job.status = JobStatus.QUEUED
        job.run_after = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
    else:
        ensure_transition(JobStatus, job.status, JobStatus.FAILED_FINAL)
        job.status = JobStatus.FAILED_FINAL
        job.last_error = error
    job.locked_at = None
    job.lock_owner = None
    db.add(job)
