from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nanoni.domain.enums import ApprovalDecision, CandidateStatus
from nanoni.domain.models import (
    Approval,
    ContentCandidate,
    ContentPack,
    ContentPackMicroNiche,
    MediaAsset,
    PackItem,
    Source,
)
from nanoni.domain.schemas import MediaManifest


def import_manifest(db: Session, *, source_id: str, manifest: MediaManifest) -> ContentCandidate:
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
        return existing
    candidate = ContentCandidate(
        source_id=source_id,
        source_item_id=manifest.source_item_id,
        source_collection_id=manifest.source_collection_id,
        source_url=manifest.source_url,
        title=manifest.title,
        caption=manifest.caption,
        status=CandidateStatus.PENDING_APPROVAL,
        manifest=manifest.model_dump(mode="json"),
        source_created_at=manifest.created_at,
    )
    db.add(candidate)
    source.presented_count += 1
    db.add(source)
    db.flush()
    return candidate


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
    candidate = db.get(ContentCandidate, candidate_id)
    if not candidate:
        raise ValueError("candidate not found")
    source = db.get(Source, candidate.source_id)
    db.add(
        Approval(
            candidate_id=candidate.id,
            admin_user_id=admin_user_id,
            decision=decision,
            target=target,
            notes=notes,
        )
    )
    if decision == ApprovalDecision.REJECTED:
        candidate.status = CandidateStatus.REJECTED
        db.add(candidate)
        db.flush()
        return None
    if decision != ApprovalDecision.APPROVED:
        candidate.status = CandidateStatus.PENDING_APPROVAL
        db.add(candidate)
        db.flush()
        return None

    candidate.status = CandidateStatus.APPROVED
    pack = ContentPack(
        candidate_id=candidate.id, title=candidate.title, caption=candidate.caption, approved=True
    )
    db.add(pack)
    db.flush()
    selected = set(selected_positions) if selected_positions is not None else None
    media = candidate.manifest.get("media", [])
    for position, item in enumerate(media):
        if selected is not None and position not in selected:
            continue
        asset = MediaAsset(
            candidate_id=candidate.id,
            media_type=item.get("media_type", "VIDEO"),
            source_locator=item.get("source_locator"),
            mime=item.get("mime"),
            duration_seconds=item.get("duration_seconds"),
            width=item.get("width"),
            height=item.get("height"),
            file_size=item.get("file_size"),
            thumbnail_ref=item.get("thumbnail_ref"),
            metadata_json=item.get("metadata") or {},
        )
        db.add(asset)
        db.flush()
        db.add(PackItem(pack_id=pack.id, asset_id=asset.id, position=position, selected=True))
    for microniche_id in dict.fromkeys(microniche_ids):
        db.add(ContentPackMicroNiche(pack_id=pack.id, microniche_id=microniche_id))
    if source:
        source.approval_count += 1
        db.add(source)
    db.add(candidate)
    db.flush()
    return pack


def replace_pack_microniches(db: Session, pack_id: str, microniche_ids: list[str]) -> None:
    db.execute(delete(ContentPackMicroNiche).where(ContentPackMicroNiche.pack_id == pack_id))
    for microniche_id in dict.fromkeys(microniche_ids):
        db.add(ContentPackMicroNiche(pack_id=pack_id, microniche_id=microniche_id))
