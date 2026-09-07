from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from nanoni.domain.enums import (
    AssetStatus,
    DestinationStatus,
    JobType,
    PackStatus,
    PublicationStatus,
)
from nanoni.domain.models import (
    ContentPack,
    Job,
    MediaAsset,
    PackItem,
    Publication,
    PublicationJob,
    PublicationRule,
    TelegramDestination,
    Topic,
    VaultObject,
)
from nanoni.integrations.telegram.publisher import (
    PublishMedia,
    TelegramPublisher,
    TelegramPublisherOutcomeUnknown,
)
from nanoni.jobs.engine import enqueue
from nanoni.media.runtime import ensure_within


class PublicationOutcomeUnknownError(RuntimeError):
    pass


def publication_idempotency_key(pack_id: str, destination_id: str, topic_id: str | None) -> str:
    return f"publish:{pack_id}:{destination_id}:{topic_id or '-'}"


def enqueue_publication(
    db: Session,
    *,
    pack_id: str,
    destination_id: str,
    scheduled_for: datetime | None = None,
    topic_id: str | None = None,
    rule_id: str | None = None,
) -> tuple[PublicationJob, Job]:
    pack = db.get(ContentPack, pack_id)
    if not pack or not pack.approved or pack.status != PackStatus.READY:
        raise ValueError("only an approved ready pack can be published")
    destination = db.get(TelegramDestination, destination_id)
    if not destination or destination.status != DestinationStatus.ACTIVE:
        raise ValueError("active Telegram destination not found")
    topic = db.get(Topic, topic_id) if topic_id else None
    if topic_id and (not topic or not topic.active or topic.destination_id != destination.id):
        raise ValueError("active topic does not belong to the destination")
    rule = db.get(PublicationRule, rule_id) if rule_id else None
    if rule_id and (
        not rule
        or not rule.active
        or rule.destination_id != destination.id
        or rule.topic_id != topic_id
    ):
        raise ValueError("active publication rule does not match the destination and topic")

    items = list(
        db.scalars(
            select(PackItem)
            .where(PackItem.pack_id == pack.id, PackItem.selected.is_(True))
            .order_by(PackItem.position)
        )
    )
    if not items:
        raise ValueError("publication pack has no selected media")
    for item in items:
        asset = db.get(MediaAsset, item.asset_id)
        if not asset or not asset.telegram_file_id:
            raise ValueError("all selected media must have a Telegram file reference")

    key = publication_idempotency_key(pack.id, destination.id, topic_id)
    publication_job = db.scalar(
        select(PublicationJob).where(PublicationJob.idempotency_key == key)
    )
    if publication_job is None:
        publication_job = PublicationJob(
            idempotency_key=key,
            pack_id=pack.id,
            destination_id=destination.id,
            topic_id=topic_id,
            rule_id=rule_id,
            scheduled_for=scheduled_for or datetime.now(UTC),
            status=PublicationStatus.SCHEDULED,
        )
        db.add(publication_job)
        db.flush()
    dispatch = enqueue(
        db,
        job_type=JobType.PUBLISH_CONTENT,
        payload={"publication_job_id": publication_job.id},
        idempotency_key=f"dispatch-publication:{publication_job.id}",
        run_after=publication_job.scheduled_for,
        max_attempts=5,
    )
    return publication_job, dispatch


def publish_publication_job(
    db: Session,
    *,
    publication_job_id: str,
    publisher: TelegramPublisher,
) -> Publication:
    publication_job = db.get(PublicationJob, publication_job_id)
    if not publication_job:
        raise ValueError("publication job not found")
    existing = db.scalar(
        select(Publication).where(Publication.publication_job_id == publication_job.id)
    )
    if existing:
        publication_job.status = PublicationStatus.PUBLISHED
        publication_job.last_error = None
        db.add(publication_job)
        db.flush()
        return existing
    if publication_job.status == PublicationStatus.PUBLISHING:
        raise PublicationOutcomeUnknownError(
            "publication attempt has no confirmed Telegram references"
        )

    pack = db.get(ContentPack, publication_job.pack_id)
    destination = db.get(TelegramDestination, publication_job.destination_id)
    topic = db.get(Topic, publication_job.topic_id) if publication_job.topic_id else None
    if not pack or not pack.approved or pack.status != PackStatus.READY:
        raise ValueError("only an approved ready pack can be published")
    if not destination or destination.status != DestinationStatus.ACTIVE:
        raise ValueError("active Telegram destination not found")
    if publication_job.topic_id and (
        not topic or not topic.active or topic.destination_id != destination.id
    ):
        raise ValueError("active topic does not belong to the destination")

    items = list(
        db.scalars(
            select(PackItem)
            .where(PackItem.pack_id == pack.id, PackItem.selected.is_(True))
            .order_by(PackItem.position)
        )
    )
    media: list[PublishMedia] = []
    assets: list[MediaAsset] = []
    for item in items:
        asset = db.get(MediaAsset, item.asset_id)
        if not asset or not asset.telegram_file_id:
            raise ValueError("all selected media must have a Telegram file reference")
        assets.append(asset)
        media.append(PublishMedia(file_id=asset.telegram_file_id, media_type=asset.media_type))
    if not media:
        raise ValueError("publication pack has no selected media")

    claimed = db.execute(
        update(PublicationJob)
        .where(
            PublicationJob.id == publication_job.id,
            PublicationJob.status.in_(
                [
                    PublicationStatus.QUEUED,
                    PublicationStatus.SCHEDULED,
                    PublicationStatus.FAILED,
                ]
            ),
        )
        .values(
            status=PublicationStatus.PUBLISHING,
            attempts=PublicationJob.attempts + 1,
            last_error=None,
        )
    )
    if claimed.rowcount != 1:
        db.rollback()
        raise PublicationOutcomeUnknownError("publication attempt was claimed concurrently")
    db.commit()
    try:
        sent = publisher.publish_pack(
            chat_id=destination.telegram_chat_id,
            media=media,
            caption=pack.caption,
            message_thread_id=topic.message_thread_id if topic else None,
            protect_content=destination.protected_content,
        )
    except TelegramPublisherOutcomeUnknown as exc:
        publication_job.last_error = "Telegram publication outcome requires manual reconciliation"
        db.add(publication_job)
        db.commit()
        raise PublicationOutcomeUnknownError(publication_job.last_error) from exc
    except Exception:
        publication_job.status = PublicationStatus.FAILED
        db.add(publication_job)
        db.commit()
        raise

    publication = Publication(
        publication_job_id=publication_job.id,
        pack_id=pack.id,
        destination_id=destination.id,
        topic_id=topic.id if topic else None,
        telegram_message_ids=list(sent.message_ids),
    )
    publication_job.status = PublicationStatus.PUBLISHED
    publication_job.last_error = None
    for asset in assets:
        asset.status = AssetStatus.PUBLISHED
    db.add_all([publication_job, publication, *assets])
    db.flush()
    return publication


def purge_confirmed_publication_files(
    db: Session, *, publication_id: str, media_root: Path
) -> list[Path]:
    publication = db.get(Publication, publication_id)
    if not publication or not publication.telegram_message_ids:
        raise ValueError("confirmed publication not found")
    items = list(
        db.scalars(
            select(PackItem).where(
                PackItem.pack_id == publication.pack_id,
                PackItem.selected.is_(True),
            )
        )
    )
    removed: list[Path] = []
    for item in items:
        asset = db.get(MediaAsset, item.asset_id)
        if not asset or not asset.local_path:
            continue
        vault = db.scalar(
            select(VaultObject).where(
                VaultObject.asset_id == asset.id,
                VaultObject.verified_at.is_not(None),
            )
        )
        if not vault:
            continue
        path = ensure_within(media_root, Path(asset.local_path))
        if path.is_file():
            path.unlink()
            removed.append(path)
        asset.local_path = None
        asset.status = AssetStatus.PURGED
        db.add(asset)
    db.flush()
    return removed
