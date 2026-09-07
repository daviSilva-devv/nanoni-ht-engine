from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select

from nanoni.core.config import get_settings
from nanoni.domain.enums import AssetStatus
from nanoni.domain.models import ContentCandidate, MediaAsset, PackItem, Source


@pytest.fixture
def helper_media_root(tmp_path):
    settings = get_settings()
    previous = settings.media_root
    settings.media_root = tmp_path
    try:
        yield tmp_path
    finally:
        settings.media_root = previous


def _manifest_body() -> bytes:
    return json.dumps(
        {
            "source_id": None,
            "manifest": {
                "source": "telegram-helper",
                "source_item_id": "/k/:message-42",
                "source_url": "https://web.telegram.org/k/#channel",
                "title": "Channel",
                "caption": "Visible post caption",
                "media": [
                    {
                        "external_item_id": "message-42:image:0",
                        "media_type": "IMAGE",
                        "source_reference": "blob:https://web.telegram.org/context-only",
                        "downloadable": False,
                        "metadata": {"browser_detected": True},
                    }
                ],
                "metadata": {"assisted_import": True, "detected_media_count": 1},
            },
        },
        separators=(",", ":"),
    ).encode()


def _signature(message: bytes) -> str:
    return hmac.new(
        get_settings().helper_shared_secret.encode(), message, hashlib.sha256
    ).hexdigest()


def test_signed_helper_context_creates_candidate_and_source_idempotently(client, db):
    body = _manifest_body()
    headers = {
        "Content-Type": "application/json",
        "X-Nanoni-Signature": _signature(body),
    }
    first = client.post("/api/v1/content/helper/manifest", content=body, headers=headers)
    second = client.post("/api/v1/content/helper/manifest", content=body, headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["pack_id"] == first.json()["pack_id"]
    assert second.json()["import_classification"] == "SAME_SOURCE_ITEM"
    candidate = db.get(ContentCandidate, first.json()["id"])
    assert candidate and candidate.caption == "Visible post caption"
    assert db.scalar(
        select(func.count(Source.id)).where(Source.adapter == "telegram-helper")
    ) == 1


def test_helper_rejects_unsigned_context(client):
    response = client.post(
        "/api/v1/content/helper/manifest",
        content=_manifest_body(),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_authorized_file_is_linked_to_same_candidate_and_replay_is_idempotent(
    client, db, helper_media_root
):
    body = _manifest_body()
    imported = client.post(
        "/api/v1/content/helper/manifest",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Nanoni-Signature": _signature(body),
        },
    ).json()
    candidate_id = imported["id"]
    timestamp = str(int(time.time()))
    signature = _signature(f"{timestamp}:{candidate_id}".encode())
    url = f"/api/v1/content/helper/candidates/{candidate_id}/files"
    headers = {
        "X-Nanoni-Timestamp": timestamp,
        "X-Nanoni-Signature": signature,
    }

    first = client.post(
        url,
        headers=headers,
        files=[("files", ("authorized.png", b"operator-authorized", "image/png"))],
    )
    second = client.post(
        url,
        headers=headers,
        files=[("files", ("authorized.png", b"operator-authorized", "image/png"))],
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert second.json()["asset_ids"] == first.json()["asset_ids"]
    assert db.scalar(select(func.count(PackItem.id))) == 1
    asset = db.get(MediaAsset, first.json()["asset_ids"][0])
    assert asset and asset.status == AssetStatus.LOCAL_READY
    assert asset.sha256 == hashlib.sha256(b"operator-authorized").hexdigest()
    assert asset.local_path and Path(asset.local_path).is_file()
    assert helper_media_root.resolve() in Path(asset.local_path).resolve().parents

    Path(asset.local_path).unlink()
    asset.local_path = None
    asset.status = AssetStatus.PURGED
    db.commit()
    restored = client.post(
        url,
        headers=headers,
        files=[("files", ("authorized.png", b"operator-authorized", "image/png"))],
    )
    assert restored.status_code == 201
    assert restored.json()["asset_ids"] == first.json()["asset_ids"]
    db.refresh(asset)
    assert asset.local_path and Path(asset.local_path).is_file()
    assert asset.status == AssetStatus.LOCAL_READY


def test_authorized_file_rejects_stale_signature(client):
    candidate_id = "candidate"
    timestamp = str(int(time.time()) - 301)
    response = client.post(
        f"/api/v1/content/helper/candidates/{candidate_id}/files",
        headers={
            "X-Nanoni-Timestamp": timestamp,
            "X-Nanoni-Signature": _signature(f"{timestamp}:{candidate_id}".encode()),
        },
        files=[("files", ("authorized.png", b"file", "image/png"))],
    )
    assert response.status_code == 401
