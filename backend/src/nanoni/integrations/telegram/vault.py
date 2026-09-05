from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import AssetStatus, DestinationType, JobType, PackStatus
from nanoni.domain.models import (
    ContentPack,
    Job,
    MediaAsset,
    PackItem,
    TelegramDestination,
    VaultObject,
)
from nanoni.integrations.telegram.media_gateway import TelegramMediaGateway
from nanoni.jobs.engine import enqueue
from nanoni.media.runtime import original_file


def ensure_vault_destination(db: Session, chat_id: str) -> TelegramDestination:
    destination = db.scalar(
        select(TelegramDestination).where(TelegramDestination.telegram_chat_id == chat_id)
    )
    if destination:
        if destination.destination_type != DestinationType.VAULT_CHANNEL:
            raise ValueError("configured Telegram chat is not a vault destination")
        return destination
    destination = TelegramDestination(
        name="Private Media Vault",
        destination_type=DestinationType.VAULT_CHANNEL,
        telegram_chat_id=chat_id,
    )
    db.add(destination)
    db.flush()
    return destination


def enqueue_pack_vault_uploads(db: Session, *, pack_id: str, vault_chat_id: str) -> list[Job]:
    if not vault_chat_id:
        raise ValueError("Telegram vault chat ID is not configured")
    pack = db.get(ContentPack, pack_id)
    if not pack or not pack.approved or pack.status != PackStatus.READY:
        raise ValueError("only an approved ready pack can be vaulted")
    ensure_vault_destination(db, vault_chat_id)
    items = list(
        db.scalars(
            select(PackItem)
            .where(PackItem.pack_id == pack_id, PackItem.selected.is_(True))
            .order_by(PackItem.position)
        )
    )
    jobs: list[Job] = []
    for item in items:
        asset = db.get(MediaAsset, item.asset_id)
        if not asset:
            raise ValueError("selected pack item has no media asset")
        if (
            asset.telegram_file_id
            and asset.vault_message_id
            and asset.vault_chat_id == vault_chat_id
        ):
            continue
        if not asset.local_path or not Path(asset.local_path).is_file():
            raise ValueError("selected media must be locally ready before vault upload")
        jobs.append(
            enqueue(
                db,
                job_type=JobType.UPLOAD_VAULT,
                payload={"asset_id": asset.id, "vault_chat_id": vault_chat_id},
                idempotency_key=f"upload-vault:{asset.id}:{vault_chat_id}",
                max_attempts=5,
            )
        )
    db.flush()
    return jobs


def upload_asset_to_vault(
    db: Session,
    *,
    asset_id: str,
    vault_chat_id: str,
    media_root: Path,
    gateway: TelegramMediaGateway,
    progress: Callable[[int, int], None] | None = None,
) -> VaultObject:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise ValueError("media asset not found")
    existing = db.scalar(select(VaultObject).where(VaultObject.asset_id == asset.id))
    if (
        existing
        and existing.verified_at
        and asset.telegram_file_id
        and asset.vault_message_id
        and asset.vault_chat_id == vault_chat_id
    ):
        return existing
    if not asset.local_path:
        raise ValueError("media asset has no local file")
    path = original_file(asset.local_path, media_root)
    destination = ensure_vault_destination(db, vault_chat_id)
    uploaded = gateway.upload(
        chat_id=vault_chat_id,
        path=path,
        media_type=asset.media_type,
        mime_type=asset.mime,
        progress=progress,
    )
    verified_at = datetime.now(UTC)
    if existing is None:
        existing = VaultObject(
            asset_id=asset.id,
            destination_id=destination.id,
            telegram_message_id=uploaded.message_id,
        )
    existing.destination_id = destination.id
    existing.telegram_message_id = uploaded.message_id
    existing.telegram_file_id = uploaded.file_id
    existing.verified_at = verified_at
    existing.metadata_json = {"file_unique_id": uploaded.file_unique_id}
    asset.telegram_file_id = uploaded.file_id
    asset.telegram_file_unique_id = uploaded.file_unique_id
    asset.vault_chat_id = vault_chat_id
    asset.vault_message_id = uploaded.message_id
    asset.status = AssetStatus.VAULTED
    db.add_all([asset, existing])
    db.flush()
    return existing
