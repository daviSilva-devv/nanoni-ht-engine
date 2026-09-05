from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.models import MediaAsset
from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.domain.services.content import import_manifest_with_classification
from nanoni.media.importer import ensure_manual_source
from nanoni.media.runtime import (
    SUPPORTED_EXTENSIONS,
    ensure_runtime_layout,
    internal_filename,
    media_type_for,
    move_without_overwrite,
    sha256_file,
)


@dataclass(frozen=True)
class WatchScan:
    candidate_ids: list[str]
    failed_files: list[str]
    recovered_files: list[str]


def _already_persisted(db: Session, path: Path) -> bool:
    return (
        db.scalar(
            select(MediaAsset.id).where(MediaAsset.local_path == str(path.resolve())).limit(1)
        )
        is not None
    )


def _import_processing_file(
    db: Session, *, path: Path, original_filename: str, recovered: bool
) -> str:
    digest = sha256_file(path)
    existing = db.scalar(
        select(MediaAsset)
        .where(MediaAsset.sha256 == digest, MediaAsset.local_path.is_not(None))
        .limit(1)
    )
    local_path = path
    if existing and existing.local_path and Path(existing.local_path).is_file():
        path.unlink()
        local_path = Path(existing.local_path)
    source = ensure_manual_source(db)
    external_id = path.name
    manifest = MediaManifest(
        source="manual",
        source_external_id=f"watch:{external_id}",
        source_collection_id=f"watch:{external_id}",
        title=original_filename,
        media=[
            ManifestAsset(
                external_item_id=external_id,
                media_type=media_type_for(path),
                source_reference=f"watch://{external_id}",
                original_filename=original_filename,
                file_size=local_path.stat().st_size,
                sha256=digest,
                local_path=str(local_path.resolve()),
                metadata={"ingest": "watch-folder", "recovered": recovered},
            )
        ],
        metadata={"ingest": "watch-folder"},
    )
    outcome = import_manifest_with_classification(db, source_id=source.id, manifest=manifest)
    return outcome.candidate.id


def scan_watch_folder(db: Session, *, root: Path) -> WatchScan:
    layout = ensure_runtime_layout(root)
    candidate_ids: list[str] = []
    failed_files: list[str] = []
    recovered_files: list[str] = []

    for source_path in sorted(path for path in layout["inbox"].iterdir() if path.is_file()):
        original_filename = source_path.name
        destination = layout["processing"] / internal_filename(source_path.name)
        try:
            processing_path = move_without_overwrite(source_path, destination)
            if source_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                failed_destination = layout["failed"] / destination.name
                if not failed_destination.suffix:
                    failed_destination = failed_destination.with_suffix(".invalid")
                move_without_overwrite(processing_path, failed_destination)
                failed_files.append(original_filename)
                continue
            with db.begin_nested():
                candidate_id = _import_processing_file(
                    db, path=processing_path, original_filename=original_filename, recovered=False
                )
            candidate_ids.append(candidate_id)
        except Exception:
            if destination.exists():
                failed_destination = layout["failed"] / destination.name
                if not failed_destination.exists():
                    destination.rename(failed_destination)
            failed_files.append(original_filename)

    for processing_path in sorted(
        path for path in layout["processing"].iterdir() if path.is_file()
    ):
        if _already_persisted(db, processing_path):
            continue
        try:
            with db.begin_nested():
                candidate_id = _import_processing_file(
                    db,
                    path=processing_path,
                    original_filename=processing_path.name,
                    recovered=True,
                )
            candidate_ids.append(candidate_id)
            recovered_files.append(processing_path.name)
        except Exception:
            failed_destination = layout["failed"] / processing_path.name
            if not failed_destination.exists():
                processing_path.rename(failed_destination)
            failed_files.append(processing_path.name)

    db.flush()
    return WatchScan(candidate_ids, failed_files, recovered_files)


def import_inbox_once(db: Session, *, root: Path) -> list[str]:
    return scan_watch_folder(db, root=root).candidate_ids


def watch_folder_status(root: Path) -> tuple[dict[str, str], dict[str, int]]:
    layout = ensure_runtime_layout(root)
    folders = {
        name: str(layout[name]) for name in ("inbox", "processing", "ready", "failed", "temp")
    }
    counts = {
        name: sum(1 for path in layout[name].iterdir() if path.is_file())
        for name in ("inbox", "processing", "ready", "failed", "temp")
    }
    return folders, counts
