from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.models import Job
from nanoni.jobs.engine import enqueue

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_admin)])


@router.get("")
def list_jobs(status_filter: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Job).order_by(Job.created_at.desc()).limit(200)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    rows = list(db.scalars(stmt))
    return [
        {
            "id": row.id,
            "type": row.type,
            "status": row.status,
            "attempts": row.attempts,
            "max_attempts": row.max_attempts,
            "run_after": row.run_after,
            "last_error": row.last_error,
            "payload": row.payload,
        }
        for row in rows
    ]


@router.post("/enqueue")
def enqueue_job(
    job_type: str, payload: dict, idempotency_key: str | None = None, db: Session = Depends(get_db)
):
    job = enqueue(db, job_type=job_type, payload=payload, idempotency_key=idempotency_key)
    db.commit()
    return {"id": job.id, "status": job.status}
