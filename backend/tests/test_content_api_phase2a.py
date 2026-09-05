from pathlib import Path

import pytest
from sqlalchemy import select

from nanoni.core.config import get_settings
from nanoni.domain.models import MediaAsset, PackItem, Source


@pytest.fixture
def phase2_media_root(tmp_path):
    settings = get_settings()
    previous = settings.media_root
    settings.media_root = tmp_path
    try:
        yield tmp_path
    finally:
        settings.media_root = previous


def test_content_api_requires_admin_token(client, admin_headers):
    assert client.get("/api/v1/content/candidates").status_code == 401
    assert client.get("/api/v1/content/candidates", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/content/watch-folder/status").status_code == 401


def test_manual_multi_upload_creates_one_pack_and_preserves_safe_originals(
    client, db, admin_headers, phase2_media_root
):
    response = client.post(
        "/api/v1/content/manual-import",
        headers=admin_headers,
        data={"title": "Mixed upload"},
        files=[
            ("files", ("../../photo.jpg", b"photo", "image/jpeg")),
            ("files", ("clip.mp4", b"video", "video/mp4")),
        ],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["import_classification"] == "NEW"

    detail = client.get(f"/api/v1/content/packs/{body['pack_id']}", headers=admin_headers)
    assert detail.status_code == 200
    pack = detail.json()
    assert pack["status"] == "REVIEW"
    assert len(pack["items"]) == 2
    assert [item["original_filename"] for item in pack["items"]] == [
        "../../photo.jpg",
        "clip.mp4",
    ]
    for asset in db.scalars(select(MediaAsset)):
        local_path = Path(asset.local_path).resolve()
        assert phase2_media_root.resolve() in local_path.parents
        assert local_path.parent.name == "processing"

    asset_id = pack["items"][0]["asset"]["id"]
    assert client.get(f"/api/v1/content/assets/{asset_id}/original").status_code == 401
    original = client.get(f"/api/v1/content/assets/{asset_id}/original", headers=admin_headers)
    assert original.status_code == 200
    assert original.content == b"photo"
    assert original.headers["content-disposition"].startswith("inline;")

    ranged = client.get(
        f"/api/v1/content/assets/{asset_id}/original",
        headers={**admin_headers, "Range": "bytes=1-3"},
    )
    assert ranged.status_code == 206
    assert ranged.content == b"hot"
    assert ranged.headers["content-range"] == "bytes 1-3/5"


def test_content_api_detail_edit_selection_reorder_and_decisions(
    client, db, admin_headers, phase2_media_root
):
    response = client.post(
        "/api/v1/content/manual-import",
        headers=admin_headers,
        files=[
            ("files", ("1.jpg", b"1", "image/jpeg")),
            ("files", ("2.jpg", b"2", "image/jpeg")),
            ("files", ("3.mp4", b"3", "video/mp4")),
        ],
    )
    body = response.json()
    candidate_id = body["id"]
    pack_id = body["pack_id"]

    candidate = client.get(f"/api/v1/content/candidates/{candidate_id}", headers=admin_headers)
    assert candidate.status_code == 200
    assert candidate.json()["pack_id"] == pack_id

    selected = client.put(
        f"/api/v1/content/packs/{pack_id}/selection",
        headers=admin_headers,
        json={"selected_positions": [1, 3]},
    )
    assert [item["selected"] for item in selected.json()["items"]] == [True, False, True]

    item_ids = [item["id"] for item in selected.json()["items"]]
    reordered = client.put(
        f"/api/v1/content/packs/{pack_id}/order",
        headers=admin_headers,
        json={"item_ids": list(reversed(item_ids))},
    )
    assert [item["id"] for item in reordered.json()["items"]] == list(reversed(item_ids))

    edited = client.patch(
        f"/api/v1/content/packs/{pack_id}",
        headers=admin_headers,
        json={"title": "Edited", "tags": ["Tag A", "Tag B"]},
    )
    assert edited.status_code == 200
    assert edited.json()["tags"] == ["Tag A", "Tag B"]

    approved = client.post(
        f"/api/v1/content/candidates/{candidate_id}/approve",
        headers=admin_headers,
        json={"selected_positions": [1, 3], "target": "VIP"},
    )
    assert approved.status_code == 200
    ready = client.get(f"/api/v1/content/packs/{pack_id}", headers=admin_headers).json()
    assert ready["status"] == "READY"
    assert len(list((phase2_media_root / "ready").iterdir())) == 2
    assert len(list((phase2_media_root / "processing").iterdir())) == 1
    assert len(list(db.scalars(select(PackItem).where(PackItem.pack_id == pack_id)))) == 3


def test_duplicate_classification_endpoint(client, db, admin_headers):
    source = Source(name="Source", adapter="manual")
    db.add(source)
    db.commit()
    manifest = {
        "source": "manual",
        "source_external_id": "candidate-1",
        "media": [
            {
                "external_item_id": "item-1",
                "media_type": "IMAGE",
                "sha256": "a" * 64,
            }
        ],
    }
    payload = {"source_id": source.id, "manifest": manifest}
    first = client.post("/api/v1/content/candidates/import", headers=admin_headers, json=payload)
    assert first.status_code == 201
    duplicate = client.post(
        "/api/v1/content/duplicates/classify", headers=admin_headers, json=payload
    )
    assert duplicate.json() == {"classification": "SAME_SOURCE_ITEM"}


def test_original_asset_path_traversal_is_blocked(
    client, db, admin_headers, phase2_media_root, tmp_path
):
    outside = tmp_path.parent / "outside-phase2.jpg"
    outside.write_bytes(b"outside")
    asset = MediaAsset(media_type="IMAGE", local_path=str(outside), original_filename="outside.jpg")
    db.add(asset)
    db.commit()
    response = client.get(f"/api/v1/content/assets/{asset.id}/original", headers=admin_headers)
    assert response.status_code == 404
