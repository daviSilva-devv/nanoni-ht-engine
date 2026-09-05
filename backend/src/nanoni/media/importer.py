from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.models import MediaAsset, Source
from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.domain.services.content import ImportOutcome, import_manifest_with_classification
from nanoni.media.runtime import (
    ensure_runtime_layout,
    internal_filename,
    media_type_for,
    move_without_overwrite,
    sha256_file,
)


def ensure_manual_source(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.adapter == "manual").order_by(Source.created_at))
    if source:
        return source
    source = Source(name="Manual Inbox", adapter="manual")
    db.add(source)
    db.flush()
    return source


def _existing_blob_path(db: Session, digest: str) -> Path | None:
    asset = db.scalar(
        select(MediaAsset)
        .where(MediaAsset.sha256 == digest, MediaAsset.local_path.is_not(None))
        .limit(1)
    )
    if asset and asset.local_path and Path(asset.local_path).is_file():
        return Path(asset.local_path).resolve()
    return None


def _write_stream(stream: BinaryIO, destination: Path) -> None:
    with destination.open("xb") as handle:
        while chunk := stream.read(1024 * 1024):
            handle.write(chunk)


def import_streams(
    db: Session,
    *,
    files: Iterable[tuple[str, str | None, BinaryIO]],
    root: Path,
    title: str | None = None,
) -> ImportOutcome:
    layout = ensure_runtime_layout(root)
    collection_id = uuid4().hex
    manifest_items: list[ManifestAsset] = []
    created_paths: list[Path] = []
    batch_blobs: dict[str, Path] = {}
    try:
        for original_filename, mime_type, stream in files:
            probe = Path(original_filename)
            media_type = media_type_for(probe)
            internal_name = internal_filename(original_filename)
            inbox_path = layout["inbox"] / internal_name
            _write_stream(stream, inbox_path)
            created_paths.append(inbox_path)
            processing_path = move_without_overwrite(
                inbox_path, layout["processing"] / internal_name
            )
            created_paths[-1] = processing_path
            digest = sha256_file(processing_path)
            existing_path = batch_blobs.get(digest) or _existing_blob_path(db, digest)
            local_path = processing_path
            if existing_path:
                processing_path.unlink()
                created_paths.remove(processing_path)
                local_path = existing_path
            else:
                batch_blobs[digest] = processing_path

            manifest_items.append(
                ManifestAsset(
                    external_item_id=uuid4().hex,
                    media_type=media_type,
                    source_reference=f"manual://{collection_id}/{internal_name}",
                    original_filename=original_filename[:500],
                    mime_type=mime_type,
                    file_size=local_path.stat().st_size,
                    sha256=digest,
                    local_path=str(local_path),
                    metadata={"ingest": "manual-upload"},
                )
            )

        if not manifest_items:
            raise ValueError("at least one file is required")
        source = ensure_manual_source(db)
        manifest = MediaManifest(
            source="manual",
            source_external_id=collection_id,
            source_collection_id=collection_id,
            title=title or manifest_items[0].original_filename,
            media=manifest_items,
            metadata={"ingest": "manual-upload"},
        )
        return import_manifest_with_classification(db, source_id=source.id, manifest=manifest)
    except Exception:
        for path in created_paths:
            if path.exists():
                failed_path = layout["failed"] / path.name
                if not failed_path.exists():
                    path.rename(failed_path)
        raise
