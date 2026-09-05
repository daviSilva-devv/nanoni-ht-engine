from __future__ import annotations

import logging
import time
from collections.abc import Callable

from nanoni.core.config import get_settings
from nanoni.core.db import SessionLocal
from nanoni.domain.enums import AssetStatus
from nanoni.domain.models import Job, MediaAsset, PackItem
from nanoni.domain.services.commerce import expire_due_entitlements, fulfill_order_entitlements
from nanoni.integrations.source.erome import EromeAdapter
from nanoni.integrations.source.erome_service import acquire_pack_item
from nanoni.jobs.engine import claim_next, fail, succeed

logger = logging.getLogger(__name__)


def _fulfill_access(db, job: Job) -> None:
    fulfill_order_entitlements(db, str(job.payload["order_id"]))


def _expire_access(db, job: Job) -> None:
    expire_due_entitlements(db)


def _acquire_media(db, job: Job) -> None:
    adapter = EromeAdapter()
    try:
        item = db.get(PackItem, str(job.payload["pack_item_id"]))
        asset = db.get(MediaAsset, item.asset_id) if item else None
        if item and item.selected and asset and not asset.local_path:
            asset.status = AssetStatus.ACQUIRING
            db.commit()
        acquire_pack_item(
            db,
            pack_item_id=str(job.payload["pack_item_id"]),
            media_root=get_settings().media_root,
            adapter=adapter,
        )
    except Exception:
        db.rollback()
        item = db.get(PackItem, str(job.payload.get("pack_item_id", "")))
        asset = db.get(MediaAsset, item.asset_id) if item else None
        if asset:
            asset.status = AssetStatus.FAILED
            db.commit()
        raise
    finally:
        adapter.client.close()


HANDLERS: dict[str, Callable] = {
    "FULFILL_ACCESS": _fulfill_access,
    "EXPIRE_ACCESS": _expire_access,
    "ACQUIRE_MEDIA": _acquire_media,
}


def run_once(worker_id: str = "local-worker") -> bool:
    db = SessionLocal()
    try:
        job = claim_next(db, worker_id)
        if not job:
            db.rollback()
            return False
        db.commit()
        handler = HANDLERS.get(job.type)
        if not handler:
            fail(db, job, f"no handler registered for {job.type}", retry_delay_seconds=60)
            db.commit()
            return True
        try:
            handler(db, job)
            succeed(db, job)
            db.commit()
        except Exception as exc:  # worker boundary: persist failure rather than lose it
            db.rollback()
            job = db.get(Job, job.id)
            if job:
                fail(db, job, str(exc))
                db.commit()
            logger.exception("job failed: %s", job.id if job else "unknown")
        return True
    finally:
        db.close()


def run_forever(poll_seconds: float = 2.0) -> None:
    while True:
        if not run_once():
            time.sleep(poll_seconds)


if __name__ == "__main__":
    run_forever()
