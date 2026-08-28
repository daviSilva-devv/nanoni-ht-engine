from sqlalchemy import select

from nanoni.domain.enums import ApprovalDecision
from nanoni.domain.models import MediaAsset, PackItem, Source
from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.domain.services.content import decide_candidate, import_manifest


def test_manifest_approval_creates_pack_and_only_selected_assets(db):
    source = Source(name="Public Albums", adapter="erome")
    db.add(source)
    db.flush()
    manifest = MediaManifest(
        source="erome",
        source_collection_id="pack-a",
        source_item_id="pack-a",
        source_url="https://www.erome.com/pack-a",
        media=[
            ManifestAsset(source_locator="https://cdn/1.jpg", media_type="IMAGE"),
            ManifestAsset(source_locator="https://cdn/2.mp4", media_type="VIDEO"),
            ManifestAsset(source_locator="https://cdn/3.jpg", media_type="IMAGE"),
        ],
    )
    candidate = import_manifest(db, source_id=source.id, manifest=manifest)
    pack = decide_candidate(
        db,
        candidate_id=candidate.id,
        decision=ApprovalDecision.APPROVED,
        target="VIP",
        microniche_ids=[],
        selected_positions=[0, 1],
    )
    assert pack is not None and pack.approved
    items = list(
        db.scalars(select(PackItem).where(PackItem.pack_id == pack.id).order_by(PackItem.position))
    )
    assets = [db.get(MediaAsset, item.asset_id) for item in items]
    assert [i.position for i in items] == [0, 1]
    assert [a.media_type for a in assets] == ["IMAGE", "VIDEO"]
    assert source.approval_count == 1


def test_duplicate_manifest_is_idempotent(db):
    source = Source(name="Source", adapter="manual")
    db.add(source)
    db.flush()
    manifest = MediaManifest(source="manual", source_item_id="same", media=[])
    first = import_manifest(db, source_id=source.id, manifest=manifest)
    second = import_manifest(db, source_id=source.id, manifest=manifest)
    assert first.id == second.id
    assert source.presented_count == 1
