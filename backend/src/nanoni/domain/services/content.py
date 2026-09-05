from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nanoni.domain.enums import (
    ApprovalDecision,
    AssetStatus,
    CandidateStatus,
    DuplicateClassification,
    PackStatus,
)
from nanoni.domain.models import (
    Approval,
    ContentCandidate,
    ContentPack,
    ContentPackMicroNiche,
    ContentPackTag,
    ContentTag,
    MediaAsset,
    MicroNiche,
    PackItem,
    Source,
)
from nanoni.domain.schemas import MediaManifest, PackRead


@dataclass(frozen=True)
class ImportOutcome:
    candidate: ContentCandidate
    pack: ContentPack
    classification: DuplicateClassification


def _candidate_pack(db: Session, candidate_id: str) -> ContentPack | None:
    return db.scalar(select(ContentPack).where(ContentPack.candidate_id == candidate_id))


def _asset_for_source_item(
    db: Session, *, source_id: str, external_item_id: str | None
) -> MediaAsset | None:
    if not external_item_id:
        return None
    return db.scalar(
        select(MediaAsset)
        .join(PackItem, PackItem.asset_id == MediaAsset.id)
        .where(
            PackItem.source_id == source_id,
            PackItem.source_external_id == external_item_id,
        )
        .limit(1)
    )


def _asset_for_sha256(db: Session, sha256: str | None) -> MediaAsset | None:
    if not sha256:
        return None
    return db.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256).limit(1))


def import_manifest_with_classification(
    db: Session, *, source_id: str, manifest: MediaManifest
) -> ImportOutcome:
    source = db.get(Source, source_id)
    if not source or not source.active:
        raise ValueError("source not found or inactive")

    existing = db.scalar(
        select(ContentCandidate).where(
            ContentCandidate.source_id == source_id,
            ContentCandidate.source_item_id == manifest.source_item_id,
        )
    )
    if existing:
        pack = _candidate_pack(db, existing.id)
        if not pack:
            raise ValueError("existing candidate has no content pack")
        return ImportOutcome(existing, pack, DuplicateClassification.SAME_SOURCE_ITEM)

    candidate = ContentCandidate(
        source_id=source_id,
        source_item_id=manifest.source_item_id,
        source_collection_id=manifest.source_collection_id,
        source_url=manifest.source_url,
        title=manifest.title,
        caption=manifest.caption,
        status=CandidateStatus.PENDING_APPROVAL,
        duplicate_classification=DuplicateClassification.NEW,
        manifest=manifest.model_dump(mode="json"),
        source_created_at=manifest.discovered_at,
    )
    db.add(candidate)
    db.flush()

    pack = ContentPack(
        candidate_id=candidate.id,
        title=candidate.title,
        caption=candidate.caption,
        status=PackStatus.REVIEW,
        approved=False,
        metadata_json=manifest.metadata,
    )
    db.add(pack)
    db.flush()

    classification = DuplicateClassification.NEW
    for position, item in enumerate(manifest.media, start=1):
        asset = _asset_for_source_item(
            db, source_id=source_id, external_item_id=item.external_item_id
        )
        if asset:
            classification = DuplicateClassification.SAME_SOURCE_ITEM
        else:
            asset = _asset_for_sha256(db, item.sha256)
            if asset and classification == DuplicateClassification.NEW:
                classification = DuplicateClassification.SAME_SHA256

        if not asset:
            asset = MediaAsset(
                candidate_id=candidate.id,
                media_type=item.media_type,
                source_locator=item.source_reference,
                original_filename=item.original_filename,
                mime=item.mime_type,
                duration_seconds=item.duration_seconds,
                width=item.width,
                height=item.height,
                file_size=item.file_size,
                thumbnail_ref=item.thumbnail_ref,
                local_path=item.local_path,
                sha256=item.sha256.lower() if item.sha256 else None,
                status=AssetStatus.LOCAL_READY if item.local_path else AssetStatus.DISCOVERED,
                metadata_json=item.metadata,
            )
            db.add(asset)
            db.flush()

        db.add(
            PackItem(
                pack_id=pack.id,
                asset_id=asset.id,
                position=position,
                selected=True,
                source_id=source_id,
                source_external_id=item.external_item_id,
                source_reference=item.source_reference,
                original_filename=item.original_filename,
                metadata_json=item.metadata,
            )
        )

    candidate.duplicate_classification = classification
    source.presented_count += 1
    db.add_all([candidate, source])
    db.flush()
    return ImportOutcome(candidate, pack, classification)


def import_manifest(db: Session, *, source_id: str, manifest: MediaManifest) -> ContentCandidate:
    """Backward-compatible facade for adapters that only need the candidate."""
    return import_manifest_with_classification(db, source_id=source_id, manifest=manifest).candidate


def classify_manifest(
    db: Session, *, source_id: str, manifest: MediaManifest
) -> DuplicateClassification:
    candidate_id = db.scalar(
        select(ContentCandidate.id).where(
            ContentCandidate.source_id == source_id,
            ContentCandidate.source_item_id == manifest.source_item_id,
        )
    )
    if candidate_id:
        return DuplicateClassification.SAME_SOURCE_ITEM
    for item in manifest.media:
        if _asset_for_source_item(db, source_id=source_id, external_item_id=item.external_item_id):
            return DuplicateClassification.SAME_SOURCE_ITEM
    if any(_asset_for_sha256(db, item.sha256) for item in manifest.media if item.sha256):
        return DuplicateClassification.SAME_SHA256
    return DuplicateClassification.NEW


def set_pack_selection(db: Session, pack_id: str, selected_positions: list[int]) -> None:
    pack = db.get(ContentPack, pack_id)
    if not pack:
        raise ValueError("pack not found")
    items = list(db.scalars(select(PackItem).where(PackItem.pack_id == pack_id)))
    valid_positions = {item.position for item in items}
    requested = set(selected_positions)
    if requested.difference(valid_positions):
        raise ValueError("selected position not found in pack")
    for item in items:
        item.selected = item.position in requested
        db.add(item)
    db.flush()


def reorder_pack(db: Session, pack_id: str, item_ids: list[str]) -> None:
    pack = db.get(ContentPack, pack_id)
    if not pack:
        raise ValueError("pack not found")
    items = list(db.scalars(select(PackItem).where(PackItem.pack_id == pack_id)))
    by_id = {item.id: item for item in items}
    if len(item_ids) != len(by_id) or set(item_ids) != set(by_id):
        raise ValueError("item_ids must contain every pack item exactly once")
    for temporary_position, item_id in enumerate(item_ids, start=1):
        by_id[item_id].position = -temporary_position
    db.flush()
    for position, item_id in enumerate(item_ids, start=1):
        by_id[item_id].position = position
    db.flush()


def replace_pack_microniches(db: Session, pack_id: str, microniche_ids: list[str]) -> None:
    if not db.get(ContentPack, pack_id):
        raise ValueError("pack not found")
    db.execute(delete(ContentPackMicroNiche).where(ContentPackMicroNiche.pack_id == pack_id))
    for microniche_id in dict.fromkeys(microniche_ids):
        if not db.get(MicroNiche, microniche_id):
            raise ValueError("microniche not found")
        db.add(ContentPackMicroNiche(pack_id=pack_id, microniche_id=microniche_id))
    db.flush()


def _tag_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")


def replace_pack_tags(db: Session, pack_id: str, names: list[str]) -> None:
    if not db.get(ContentPack, pack_id):
        raise ValueError("pack not found")
    db.execute(delete(ContentPackTag).where(ContentPackTag.pack_id == pack_id))
    tags_by_slug: dict[str, str] = {}
    for name in (value.strip() for value in names if value.strip()):
        slug = _tag_slug(name)
        if not slug:
            raise ValueError("tag must contain letters or numbers")
        tags_by_slug.setdefault(slug, name)
    for slug, name in tags_by_slug.items():
        tag = db.scalar(select(ContentTag).where(ContentTag.slug == slug))
        if not tag:
            tag = ContentTag(name=name, slug=slug)
            db.add(tag)
            db.flush()
        db.add(ContentPackTag(pack_id=pack_id, tag_id=tag.id))
    db.flush()


def update_pack(
    db: Session,
    *,
    pack_id: str,
    title: str | None,
    caption: str | None,
    tags: list[str] | None,
    microniche_ids: list[str] | None,
    metadata: dict | None,
    provided_fields: set[str],
) -> ContentPack:
    pack = db.get(ContentPack, pack_id)
    if not pack:
        raise ValueError("pack not found")
    if "title" in provided_fields:
        pack.title = title
    if "caption" in provided_fields:
        pack.caption = caption
    if "metadata" in provided_fields:
        pack.metadata_json = metadata or {}
    if tags is not None:
        replace_pack_tags(db, pack_id, tags)
    if microniche_ids is not None:
        replace_pack_microniches(db, pack_id, microniche_ids)
    db.add(pack)
    db.flush()
    return pack


def _promote_selected_assets(db: Session, pack_id: str) -> None:
    from nanoni.media.runtime import promote_to_ready

    items = list(
        db.scalars(
            select(PackItem)
            .where(PackItem.pack_id == pack_id, PackItem.selected.is_(True))
            .order_by(PackItem.position)
        )
    )
    for item in items:
        asset = db.get(MediaAsset, item.asset_id)
        if not asset or not asset.local_path:
            continue
        asset.local_path = str(promote_to_ready(Path(asset.local_path)))
        asset.status = AssetStatus.LOCAL_READY
        db.add(asset)


def decide_candidate(
    db: Session,
    *,
    candidate_id: str,
    decision: str,
    target: str | None,
    microniche_ids: list[str],
    selected_positions: list[int] | None = None,
    notes: str | None = None,
    admin_user_id: str | None = None,
) -> ContentPack | None:
    decision = ApprovalDecision(decision)
    candidate = db.get(ContentCandidate, candidate_id)
    if not candidate:
        raise ValueError("candidate not found")
    pack = _candidate_pack(db, candidate.id)
    if not pack:
        raise ValueError("candidate has no content pack")

    if decision == ApprovalDecision.APPROVED and candidate.status == CandidateStatus.READY:
        return pack
    if decision == ApprovalDecision.REJECTED and candidate.status == CandidateStatus.REJECTED:
        return None
    if candidate.status in {CandidateStatus.READY, CandidateStatus.REJECTED}:
        raise ValueError("candidate decision is final")
    if decision == ApprovalDecision.DEFERRED:
        previous_defer = db.scalar(
            select(Approval.id)
            .where(
                Approval.candidate_id == candidate.id,
                Approval.decision == ApprovalDecision.DEFERRED,
            )
            .limit(1)
        )
        if previous_defer:
            return pack

    db.add(
        Approval(
            candidate_id=candidate.id,
            admin_user_id=admin_user_id,
            decision=decision,
            target=target,
            notes=notes,
        )
    )
    if microniche_ids:
        replace_pack_microniches(db, pack.id, microniche_ids)

    if decision == ApprovalDecision.REJECTED:
        candidate.status = CandidateStatus.REJECTED
        pack.status = PackStatus.REJECTED
        pack.approved = False
        pack.archived = True
        db.add_all([candidate, pack])
        db.flush()
        return None

    if decision != ApprovalDecision.APPROVED:
        candidate.status = CandidateStatus.PENDING_APPROVAL
        pack.status = PackStatus.REVIEW
        pack.approved = False
        db.add_all([candidate, pack])
        db.flush()
        return pack

    if selected_positions is not None:
        set_pack_selection(db, pack.id, selected_positions)
    selected_item_id = db.scalar(
        select(PackItem.id).where(PackItem.pack_id == pack.id, PackItem.selected.is_(True)).limit(1)
    )
    if not selected_item_id:
        raise ValueError("at least one pack item must be selected for approval")
    source = db.get(Source, candidate.source_id)
    candidate.status = CandidateStatus.READY
    pack.status = PackStatus.READY
    pack.approved = True
    pack.archived = False
    _promote_selected_assets(db, pack.id)
    if source:
        source.approval_count += 1
        db.add(source)
    db.add_all([candidate, pack])
    db.flush()
    return pack


def pack_read(db: Session, pack_id: str) -> PackRead:
    pack = db.get(ContentPack, pack_id)
    if not pack:
        raise ValueError("pack not found")
    items = list(
        db.scalars(select(PackItem).where(PackItem.pack_id == pack_id).order_by(PackItem.position))
    )
    tags = list(
        db.scalars(
            select(ContentTag.name)
            .join(ContentPackTag, ContentPackTag.tag_id == ContentTag.id)
            .where(ContentPackTag.pack_id == pack_id)
            .order_by(ContentTag.name)
        )
    )
    microniche_ids = list(
        db.scalars(
            select(ContentPackMicroNiche.microniche_id).where(
                ContentPackMicroNiche.pack_id == pack_id
            )
        )
    )
    return PackRead(
        id=pack.id,
        candidate_id=pack.candidate_id,
        title=pack.title,
        caption=pack.caption,
        status=pack.status,
        approved=pack.approved,
        archived=pack.archived,
        metadata=pack.metadata_json,
        tags=tags,
        microniche_ids=microniche_ids,
        items=[
            {
                "id": item.id,
                "position": item.position,
                "selected": item.selected,
                "role": item.role,
                "source_id": item.source_id,
                "source_external_id": item.source_external_id,
                "source_reference": item.source_reference,
                "original_filename": item.original_filename,
                "metadata": item.metadata_json,
                "asset": db.get(MediaAsset, item.asset_id),
            }
            for item in items
        ],
    )
