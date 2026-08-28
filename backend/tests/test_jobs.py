from nanoni.domain.enums import JobStatus
from nanoni.jobs.engine import claim_next, enqueue, fail, succeed


def test_job_enqueue_claim_retry_and_idempotency(db):
    one = enqueue(
        db,
        job_type="PUBLISH_CONTENT",
        payload={"pack": 1},
        idempotency_key="publish:1",
        max_attempts=2,
    )
    two = enqueue(
        db,
        job_type="PUBLISH_CONTENT",
        payload={"pack": 1},
        idempotency_key="publish:1",
        max_attempts=2,
    )
    assert one.id == two.id
    claimed = claim_next(db, "worker-A")
    assert claimed.id == one.id and claimed.status == JobStatus.RUNNING
    fail(db, claimed, "temporary", retry_delay_seconds=0)
    assert claimed.status == JobStatus.QUEUED
    claimed = claim_next(db, "worker-B")
    assert claimed.attempts == 2
    succeed(db, claimed)
    assert claimed.status == JobStatus.SUCCEEDED
