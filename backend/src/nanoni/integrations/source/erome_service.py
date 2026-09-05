from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import AssetStatus, DuplicateClassification, JobType
from nanoni.domain.models import ContentCandidate, ContentPack, Job, MediaAsset, PackItem, Source
from nanoni.domain.services.content import ImportOutcome, import_manifest_with_classification
from nanoni.integrations.source.erome import EromeAdapter
from nanoni.jobs.engine import enqueue
from nanoni.media.runtime import (
    ensure_runtime_layout,
    internal_filename,
    move_without_overwrite,
    original_file,
    sha256_file,
)


def ensure_erome_source(db: Session) -> Source:
    source = db.scalar(select(Source).where(Source.adapter == "erome").order_by(Source.created_at))
    if source:
        return source
    source = Source(name="Erome Public Albums", adapter="erome")
    db.add(source)
    db.flush()
    return source


def inspect_and_import(db: Session, locator: str, adapter: EromeAdapter) -> ImportOutcome:
    manifest = adapter.inspect(locator)
    source = ensure_erome_source(db)
    return import_manifest_with_classification(db, source_id=source.id, manifest=manifest)


def enqueue_selected_acquisition(db: Session, pack_id: str) -> list[Job]:
    pack = db.get(ContentPack, pack_id)
    if not pack or not pack.candidate_id:
        raise ValueError("content pack not found")
    candidate = db.get(ContentCandidate, pack.candidate_id)
    source = db.get(Source, candidate.source_id) if candidate else None
    if not candidate or not source or source.adapter != "erome":
        raise ValueError("content pack is not backed by Erome")

    items = list(
        db.scalars(
            select(PackItem)
            .where(PackItem.pack_id == pack_id, PackItem.selected.is_(True))
            .order_by(PackItem.position)
        )
    )
    if not items:
        raise ValueError("select at least one pack item before acquisition")

    jobs: list[Job] = []
    for item in items:
        asset = db.get(MediaAsset, item.asset_id)
        if not asset or not item.source_reference:
            raise ValueError("selected pack item has no acquirable media")
        if asset.local_path and Path(asset.local_path).is_file():
            continue
        asset.status = AssetStatus.SELECTED
        jobs.append(
            enqueue(
                db,
                job_type=JobType.ACQUIRE_MEDIA,
                payload={"pack_item_id": item.id},
                idempotency_key=f"acquire-media:{item.id}",
                max_attempts=3,
            )
        )
    db.flush()
    return jobs


def acquire_pack_item(
    db: Session,
    *,
    pack_item_id: str,
    media_root: Path,
    adapter: EromeAdapter,
) -> MediaAsset:
    item = db.get(PackItem, pack_item_id)
    asset = db.get(MediaAsset, item.asset_id) if item else None
    source = db.get(Source, item.source_id) if item and item.source_id else None
    if not item or not asset or not source or source.adapter != "erome":
        raise ValueError("Erome pack item not found")
    if not item.selected:
        return asset
    if asset.local_path:
        try:
            original_file(asset.local_path, media_root)
            asset.status = AssetStatus.LOCAL_READY
            return asset
        except (FileNotFoundError, ValueError):
            asset.local_path = None
    if not item.source_reference:
        raise ValueError("Erome pack item has no media URL")

    layout = ensure_runtime_layout(media_root)
    internal_name = internal_filename(item.original_filename or item.source_reference)
    temporary = layout["temp"] / internal_name
    asset.status = AssetStatus.ACQUIRING
    db.flush()
    downloaded = adapter.acquire(item.source_reference, temporary)
    digest = sha256_file(downloaded)

    existing = db.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.id != asset.id,
            MediaAsset.sha256 == digest,
            MediaAsset.local_path.is_not(None),
        )
        .limit(1)
    )
    existing_path: Path | None = None
    if existing and existing.local_path:
        try:
            existing_path = original_file(existing.local_path, media_root)
        except (FileNotFoundError, ValueError):
            existing_path = None

    if existing_path:
        downloaded.unlink(missing_ok=True)
        local_path = existing_path
        candidate = db.get(ContentCandidate, asset.candidate_id) if asset.candidate_id else None
        if candidate:
            candidate.duplicate_classification = DuplicateClassification.SAME_SHA256
            db.add(candidate)
    else:
        local_path = move_without_overwrite(downloaded, layout["processing"] / internal_name)

    asset.local_path = str(local_path.resolve())
    asset.sha256 = digest
    asset.file_size = local_path.stat().st_size
    asset.status = AssetStatus.LOCAL_READY
    db.add(asset)
    db.flush()
    return asset
