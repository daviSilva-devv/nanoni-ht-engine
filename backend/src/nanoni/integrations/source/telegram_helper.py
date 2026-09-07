from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import AssetStatus
from nanoni.domain.models import ContentCandidate, ContentPack, MediaAsset, PackItem, Source
from nanoni.domain.schemas import MediaManifest
from nanoni.integrations.source.base import SourceAdapter
from nanoni.media.runtime import (
    ensure_runtime_layout,
    internal_filename,
    media_type_for,
    move_without_overwrite,
    sha256_file,
)


class TelegramHelperAdapter(SourceAdapter):
    """Contract for assisted imports produced by the local browser helper.

    The helper may send post metadata and a local file path obtained through a user-
    authorized route. This adapter does not implement bypass of Telegram protected
    content controls.
    """

    name = "telegram-helper"

    def inspect(self, locator: str) -> MediaManifest:
        raise NotImplementedError(
            "helper pushes manifests to the local bridge; it is not remote-inspected"
        )

    def acquire(self, asset_locator: str, destination: Path) -> Path:
        source = Path(asset_locator)
        if not source.exists():
            raise FileNotFoundError(asset_locator)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return destination


def ensure_telegram_helper_source(db: Session) -> Source:
    source = db.scalar(
        select(Source).where(Source.adapter == TelegramHelperAdapter.name).order_by(Source.created_at)
    )
    if source:
        return source
    source = Source(name="Telegram Helper", adapter=TelegramHelperAdapter.name)
    db.add(source)
    db.flush()
    return source


def _write_stream(stream: BinaryIO, destination: Path) -> None:
    with destination.open("xb") as handle:
        while chunk := stream.read(1024 * 1024):
            handle.write(chunk)


def attach_authorized_files(
    db: Session,
    *,
    candidate_id: str,
    files: Iterable[tuple[str, str | None, BinaryIO]],
    root: Path,
) -> tuple[str, list[str]]:
    candidate = db.get(ContentCandidate, candidate_id)
    pack = db.scalar(select(ContentPack).where(ContentPack.candidate_id == candidate_id))
    if not candidate or not pack:
        raise ValueError("candidate or content pack not found")
    layout = ensure_runtime_layout(root)
    items = list(
        db.scalars(select(PackItem).where(PackItem.pack_id == pack.id).order_by(PackItem.position))
    )
    next_position = max((item.position for item in items), default=0) + 1
    claimed_item_ids: set[str] = set()
    created_paths: list[Path] = []
    attached_ids: list[str] = []
    try:
        for original_filename, mime_type, stream in files:
            media_type = media_type_for(Path(original_filename))
            internal_name = internal_filename(original_filename)
            inbox_path = layout["inbox"] / internal_name
            _write_stream(stream, inbox_path)
            created_paths.append(inbox_path)
            processing_path = move_without_overwrite(
                inbox_path, layout["processing"] / internal_name
            )
            created_paths[-1] = processing_path
            digest = sha256_file(processing_path)

            duplicate_in_pack = db.scalar(
                select(MediaAsset)
                .join(PackItem, PackItem.asset_id == MediaAsset.id)
                .where(
                    PackItem.pack_id == pack.id,
                    MediaAsset.sha256 == digest,
                    MediaAsset.local_path.is_not(None),
                )
                .limit(1)
            )
            if (
                duplicate_in_pack
                and duplicate_in_pack.local_path
                and Path(duplicate_in_pack.local_path).is_file()
            ):
                processing_path.unlink()
                created_paths.remove(processing_path)
                attached_ids.append(duplicate_in_pack.id)
                continue

            existing_blob = db.scalar(
                select(MediaAsset)
                .where(MediaAsset.sha256 == digest, MediaAsset.local_path.is_not(None))
                .limit(1)
            )
            local_path = processing_path
            if (
                existing_blob
                and existing_blob.local_path
                and Path(existing_blob.local_path).is_file()
            ):
                processing_path.unlink()
                created_paths.remove(processing_path)
                local_path = Path(existing_blob.local_path).resolve()

            matched_item = next(
                (
                    item
                    for item in items
                    if item.id not in claimed_item_ids
                    and (asset := db.get(MediaAsset, item.asset_id))
                    and not asset.local_path
                    and asset.media_type == media_type
                ),
                None,
            )
            if matched_item:
                claimed_item_ids.add(matched_item.id)
                asset = db.get(MediaAsset, matched_item.asset_id)
                assert asset is not None
            else:
                asset = MediaAsset(candidate_id=candidate.id, media_type=media_type)
                db.add(asset)
                db.flush()
                matched_item = PackItem(
                    pack_id=pack.id,
                    asset_id=asset.id,
                    position=next_position,
                    selected=True,
                    source_id=candidate.source_id,
                    source_external_id=f"authorized-local:{digest}",
                    original_filename=original_filename[:500],
                    metadata_json={"ingest": "telegram-helper-authorized-file"},
                )
                next_position += 1
                db.add(matched_item)
                items.append(matched_item)
            asset.original_filename = original_filename[:500]
            asset.mime = mime_type
            asset.extension = Path(original_filename).suffix.lower()[:16]
            asset.file_size = local_path.stat().st_size
            asset.local_path = str(local_path)
            asset.sha256 = digest
            asset.status = AssetStatus.LOCAL_READY
            asset.metadata_json = {
                **(asset.metadata_json or {}),
                "ingest": "telegram-helper-authorized-file",
            }
            db.add(asset)
            attached_ids.append(asset.id)
        if not attached_ids:
            raise ValueError("at least one file is required")
        db.flush()
        return pack.id, attached_ids
    except Exception:
        for path in created_paths:
            if path.is_file():
                failed_path = layout["failed"] / path.name
                if not failed_path.exists():
                    path.rename(failed_path)
        raise
