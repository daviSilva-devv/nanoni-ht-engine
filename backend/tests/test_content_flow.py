from pathlib import Path

import pytest
from sqlalchemy import func, select

from nanoni.domain.enums import (
    ApprovalDecision,
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
    MediaAsset,
    MicroNiche,
    Niche,
    PackItem,
    Source,
)
from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.domain.services.content import (
    decide_candidate,
    import_manifest_with_classification,
    pack_read,
    reorder_pack,
    set_pack_selection,
    update_pack,
)
from nanoni.media.runtime import ensure_runtime_layout


def _source(db) -> Source:
    source = Source(name="Manual", adapter="manual")
    db.add(source)
    db.flush()
    return source


def _mixed_manifest(external_id: str = "mixed-pack") -> MediaManifest:
    media = [
        ManifestAsset(
            external_item_id=f"item-{position}",
            source_reference=f"manual://item-{position}",
            original_filename=f"item-{position}.{'jpg' if position <= 3 else 'mp4'}",
            media_type="IMAGE" if position <= 3 else "VIDEO",
            size=position * 100,
            duration=float(position),
            metadata={"position": position},
        )
        for position in range(1, 6)
    ]
    return MediaManifest(
        source="manual",
        source_external_id=external_id,
        context=f"manual://{external_id}",
        title="3 photos and 2 videos",
        discovered_at="2026-09-05T12:00:00Z",
        media=media,
        metadata={"batch": "test"},
    )


def test_manifest_creates_candidate_pack_and_all_items_before_review(db):
    source = _source(db)
    outcome = import_manifest_with_classification(
        db, source_id=source.id, manifest=_mixed_manifest()
    )

    assert outcome.classification == DuplicateClassification.NEW
    assert outcome.candidate.status == CandidateStatus.PENDING_APPROVAL
    assert outcome.pack.status == PackStatus.REVIEW
    assert db.scalar(select(func.count(ContentCandidate.id))) == 1
    assert db.scalar(select(func.count(ContentPack.id))) == 1
    items = list(
        db.scalars(
            select(PackItem).where(PackItem.pack_id == outcome.pack.id).order_by(PackItem.position)
        )
    )
    assert len(items) == 5
    assert [item.position for item in items] == [1, 2, 3, 4, 5]
    assert [item.selected for item in items] == [True] * 5
    assert [item.original_filename for item in items] == [
        "item-1.jpg",
        "item-2.jpg",
        "item-3.jpg",
        "item-4.mp4",
        "item-5.mp4",
    ]
    first_asset = db.get(MediaAsset, items[0].asset_id)
    assert first_asset is not None
    assert first_asset.file_size == 100
    assert first_asset.duration_seconds == 1.0


def test_partial_selection_keeps_unselected_items_and_approval_is_idempotent(db):
    source = _source(db)
    outcome = import_manifest_with_classification(
        db, source_id=source.id, manifest=_mixed_manifest()
    )

    pack = decide_candidate(
        db,
        candidate_id=outcome.candidate.id,
        decision=ApprovalDecision.APPROVED,
        target="VIP",
        microniche_ids=[],
        selected_positions=[1, 3, 5],
    )
    retried = decide_candidate(
        db,
        candidate_id=outcome.candidate.id,
        decision=ApprovalDecision.APPROVED,
        target="VIP",
        microniche_ids=[],
        selected_positions=[1, 3, 5],
    )

    assert pack is not None and retried is not None
    assert pack.id == retried.id
    assert pack.status == PackStatus.READY
    assert outcome.candidate.status == CandidateStatus.READY
    items = list(
        db.scalars(select(PackItem).where(PackItem.pack_id == pack.id).order_by(PackItem.position))
    )
    assert len(items) == 5
    assert [item.selected for item in items] == [True, False, True, False, True]
    assert source.approval_count == 1


def test_pack_reorder_tags_microniches_and_metadata(db):
    source = _source(db)
    outcome = import_manifest_with_classification(
        db, source_id=source.id, manifest=_mixed_manifest()
    )
    niche = Niche(name="Niche", slug="niche")
    db.add(niche)
    db.flush()
    microniche = MicroNiche(niche_id=niche.id, name="Micro", slug="micro")
    db.add(microniche)
    db.flush()

    initial = pack_read(db, outcome.pack.id)
    reversed_ids = [item.id for item in reversed(initial.items)]
    reorder_pack(db, outcome.pack.id, reversed_ids)
    set_pack_selection(db, outcome.pack.id, [1, 3, 5])
    update_pack(
        db,
        pack_id=outcome.pack.id,
        title="Edited pack",
        caption="Caption",
        tags=["Long Form", "long-form", "Exclusive"],
        microniche_ids=[microniche.id],
        metadata={"editor": "admin"},
        provided_fields={"title", "caption", "tags", "microniche_ids", "metadata"},
    )
    result = pack_read(db, outcome.pack.id)

    assert result.title == "Edited pack"
    assert result.metadata == {"editor": "admin"}
    assert result.tags == ["Exclusive", "Long Form"]
    assert result.microniche_ids == [microniche.id]
    assert [item.id for item in result.items] == reversed_ids
    assert [item.selected for item in result.items] == [True, False, True, False, True]
    assert db.scalar(select(func.count(ContentPackTag.pack_id))) == 2
    assert db.scalar(select(func.count(ContentPackMicroNiche.pack_id))) == 1


def test_source_and_sha256_dedupe_reuse_assets_but_keep_editorial_items(db):
    source = _source(db)
    digest = "a" * 64
    first = MediaManifest(
        source="manual",
        source_external_id="pack-1",
        media=[
            ManifestAsset(
                external_item_id="source-item",
                source_reference="manual://source-item",
                media_type="IMAGE",
                sha256=digest,
            )
        ],
    )
    first_outcome = import_manifest_with_classification(db, source_id=source.id, manifest=first)
    retry = import_manifest_with_classification(db, source_id=source.id, manifest=first)
    assert retry.candidate.id == first_outcome.candidate.id
    assert retry.classification == DuplicateClassification.SAME_SOURCE_ITEM

    same_source_item = first.model_copy(
        update={"source_external_id": "pack-2", "source_item_id": "pack-2"}
    )
    source_outcome = import_manifest_with_classification(
        db, source_id=source.id, manifest=same_source_item
    )
    assert source_outcome.classification == DuplicateClassification.SAME_SOURCE_ITEM

    same_sha = MediaManifest(
        source="manual",
        source_external_id="pack-3",
        media=[
            ManifestAsset(
                external_item_id="other-source-item",
                source_reference="manual://other-source-item",
                media_type="IMAGE",
                sha256=digest,
            )
        ],
    )
    sha_outcome = import_manifest_with_classification(db, source_id=source.id, manifest=same_sha)
    assert sha_outcome.classification == DuplicateClassification.SAME_SHA256

    different = MediaManifest(
        source="manual",
        source_external_id="pack-4",
        media=[
            ManifestAsset(
                external_item_id="different",
                source_reference="manual://different",
                media_type="IMAGE",
                sha256="b" * 64,
            )
        ],
    )
    import_manifest_with_classification(db, source_id=source.id, manifest=different)

    assert db.scalar(select(func.count(MediaAsset.id))) == 2
    assert db.scalar(select(func.count(PackItem.id))) == 4


@pytest.mark.parametrize(
    ("decision", "candidate_status", "pack_status"),
    [
        (ApprovalDecision.REJECTED, CandidateStatus.REJECTED, PackStatus.REJECTED),
        (ApprovalDecision.DEFERRED, CandidateStatus.PENDING_APPROVAL, PackStatus.REVIEW),
    ],
)
def test_review_decisions_preserve_pack_items(db, decision, candidate_status, pack_status):
    source = _source(db)
    outcome = import_manifest_with_classification(
        db, source_id=source.id, manifest=_mixed_manifest(str(decision))
    )
    decide_candidate(
        db,
        candidate_id=outcome.candidate.id,
        decision=decision,
        target=None,
        microniche_ids=[],
    )
    assert outcome.candidate.status == candidate_status
    assert outcome.pack.status == pack_status
    assert (
        db.scalar(select(func.count(PackItem.id)).where(PackItem.pack_id == outcome.pack.id)) == 5
    )


def test_defer_retry_is_idempotent_and_empty_approval_is_rejected(db):
    source = _source(db)
    outcome = import_manifest_with_classification(
        db, source_id=source.id, manifest=_mixed_manifest("retry-review")
    )

    for _ in range(2):
        decide_candidate(
            db,
            candidate_id=outcome.candidate.id,
            decision=ApprovalDecision.DEFERRED,
            target=None,
            microniche_ids=[],
        )
    assert db.scalar(select(func.count(Approval.id))) == 1

    with pytest.raises(ValueError, match="at least one"):
        decide_candidate(
            db,
            candidate_id=outcome.candidate.id,
            decision=ApprovalDecision.APPROVED,
            target="VIP",
            microniche_ids=[],
            selected_positions=[],
        )


def test_approval_moves_selected_local_file_to_ready(db, tmp_path):
    layout = ensure_runtime_layout(tmp_path)
    processing = layout["processing"] / "asset.mp4"
    processing.write_bytes(b"video")
    source = _source(db)
    manifest = MediaManifest(
        source="manual",
        source_external_id="local-pack",
        media=[
            ManifestAsset(
                external_item_id="local-item",
                media_type="VIDEO",
                original_filename="original.mp4",
                local_path=str(processing),
                sha256="c" * 64,
            )
        ],
    )
    outcome = import_manifest_with_classification(db, source_id=source.id, manifest=manifest)
    decide_candidate(
        db,
        candidate_id=outcome.candidate.id,
        decision=ApprovalDecision.APPROVED,
        target="VIP",
        microniche_ids=[],
    )
    asset = db.scalar(select(MediaAsset))
    assert asset is not None
    assert Path(asset.local_path).parent == layout["ready"]
    assert Path(asset.local_path).read_bytes() == b"video"
