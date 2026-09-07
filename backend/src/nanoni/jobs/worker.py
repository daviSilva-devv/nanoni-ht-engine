from __future__ import annotations

import logging
import time
from collections.abc import Callable

from nanoni.core.config import get_settings
from nanoni.core.db import SessionLocal
from nanoni.domain.enums import AssetStatus, PublicationStatus
from nanoni.domain.models import Job, MediaAsset, PackItem, PublicationJob
from nanoni.domain.services.access import has_expired_memberships, remove_expired_memberships
from nanoni.domain.services.commerce import expire_due_entitlements, fulfill_order_entitlements
from nanoni.domain.services.publishing import (
    PublicationOutcomeUnknownError,
    publish_publication_job,
    purge_confirmed_publication_files,
)
from nanoni.integrations.source.erome import EromeAdapter
from nanoni.integrations.source.erome_service import acquire_pack_item
from nanoni.integrations.telegram.media_gateway import TelegramMediaGateway
from nanoni.integrations.telegram.publisher import BotAPITelegramPublisher
from nanoni.integrations.telegram.vault import upload_asset_to_vault
from nanoni.jobs.engine import claim_next, fail, recover_stale, succeed

logger = logging.getLogger(__name__)


def _fulfill_access(db, job: Job) -> None:
    fulfill_order_entitlements(db, str(job.payload["order_id"]))


def _expire_access(db, job: Job) -> None:
    expire_due_entitlements(db)
    if not has_expired_memberships(db):
        return
    publisher = _telegram_publisher()
    try:
        remove_expired_memberships(db, publisher=publisher)
    finally:
        publisher.close()


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


def _telegram_gateway() -> TelegramMediaGateway:
    settings = get_settings()
    return TelegramMediaGateway(
        bot_token=settings.telegram_bot_token,
        api_base_url=settings.telegram_api_base_url,
        local_api_base_url=settings.telegram_local_api_base_url,
        normal_upload_limit_bytes=settings.telegram_bot_api_max_upload_bytes,
    )


def _telegram_publisher() -> BotAPITelegramPublisher:
    settings = get_settings()
    return BotAPITelegramPublisher(
        bot_token=settings.telegram_bot_token,
        api_base_url=settings.telegram_api_base_url,
    )


def _upload_vault(db, job: Job) -> None:
    gateway = _telegram_gateway()
    asset_id = str(job.payload["asset_id"])
    last_reported = 0

    def report_progress(sent: int, total: int) -> None:
        nonlocal last_reported
        if sent < total and sent - last_reported < 5 * 1024 * 1024:
            return
        last_reported = sent
        job.payload = {**job.payload, "bytes_sent": sent, "total_bytes": total}
        db.add(job)
        db.commit()

    try:
        upload_asset_to_vault(
            db,
            asset_id=asset_id,
            vault_chat_id=str(job.payload["vault_chat_id"]),
            media_root=get_settings().media_root,
            gateway=gateway,
            progress=report_progress,
        )
    except Exception:
        db.rollback()
        asset = db.get(MediaAsset, asset_id)
        if asset:
            asset.status = AssetStatus.FAILED
            db.commit()
        raise
    finally:
        gateway.close()


def _publish_content(db, job: Job) -> None:
    publisher = _telegram_publisher()
    publication_job_id = str(job.payload["publication_job_id"])
    try:
        publication = publish_publication_job(
            db,
            publication_job_id=publication_job_id,
            publisher=publisher,
        )
        db.commit()
        purge_confirmed_publication_files(
            db,
            publication_id=publication.id,
            media_root=get_settings().media_root,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc, PublicationOutcomeUnknownError):
            job.attempts = job.max_attempts
            db.add(job)
            db.commit()
        publication_job = db.get(PublicationJob, publication_job_id)
        if (
            publication_job
            and publication_job.status != PublicationStatus.PUBLISHED
            and not isinstance(exc, PublicationOutcomeUnknownError)
        ):
            publication_job.status = PublicationStatus.FAILED
            publication_job.last_error = str(exc)
            db.commit()
        raise
    finally:
        publisher.close()


HANDLERS: dict[str, Callable] = {
    "FULFILL_ACCESS": _fulfill_access,
    "EXPIRE_ACCESS": _expire_access,
    "ACQUIRE_MEDIA": _acquire_media,
    "UPLOAD_VAULT": _upload_vault,
    "PUBLISH_CONTENT": _publish_content,
}


def run_once(worker_id: str = "local-worker") -> bool:
    db = SessionLocal()
    try:
        recover_stale(db)
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
