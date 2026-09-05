from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from nanoni.api.routers import vault as vault_router
from nanoni.domain.enums import AssetStatus, JobStatus, JobType, MediaType, PackStatus
from nanoni.domain.models import ContentPack, Job, MediaAsset, PackItem, VaultObject
from nanoni.integrations.telegram.media_gateway import (
    TelegramMediaConfigurationError,
    TelegramMediaGateway,
    VaultUpload,
)
from nanoni.integrations.telegram.vault import (
    enqueue_pack_vault_uploads,
    upload_asset_to_vault,
)
from nanoni.jobs import worker
from nanoni.jobs.engine import recover_stale


def local_ready_pack(db, tmp_path):
    ready = tmp_path / "ready"
    ready.mkdir()
    path = ready / "fixture.png"
    path.write_bytes(b"telegram-vault-fixture")
    pack = ContentPack(title="Vault pack", approved=True, status=PackStatus.READY)
    asset = MediaAsset(
        media_type=MediaType.IMAGE,
        mime="image/png",
        local_path=str(path),
        status=AssetStatus.LOCAL_READY,
    )
    db.add_all([pack, asset])
    db.flush()
    db.add(PackItem(pack_id=pack.id, asset_id=asset.id, position=1, selected=True))
    db.flush()
    return pack, asset, path


def telegram_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "ok": True,
            "result": {
                "message_id": 42,
                "photo": [
                    {"file_id": "small", "file_unique_id": "u-small"},
                    {"file_id": "file-42", "file_unique_id": "unique-42"},
                ],
            },
        },
        request=request,
    )


def test_gateway_streams_with_progress_and_uses_normal_api_for_small_file(tmp_path):
    path = tmp_path / "image.png"
    path.write_bytes(b"small-image")
    requests: list[str] = []
    progress: list[tuple[int, int]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        requests.append(str(request.url))
        return telegram_response(request)

    gateway = TelegramMediaGateway(
        bot_token="test-token",
        api_base_url="https://normal.invalid",
        local_api_base_url="http://local.invalid",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=lambda _: None,
    )
    result = gateway.upload(
        chat_id="-100123",
        path=path,
        media_type=MediaType.IMAGE,
        mime_type="image/png",
        progress=lambda sent, total: progress.append((sent, total)),
    )
    assert result == VaultUpload("42", "file-42", "unique-42")
    assert requests == ["https://normal.invalid/bottest-token/sendPhoto"]
    assert progress[-1] == (path.stat().st_size, path.stat().st_size)


def test_gateway_uses_local_api_only_above_configured_limit_and_requires_it(tmp_path):
    path = tmp_path / "large.png"
    path.write_bytes(b"large")
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request.read()
        hosts.append(request.url.host)
        return telegram_response(request)

    gateway = TelegramMediaGateway(
        bot_token="token",
        api_base_url="https://normal.invalid",
        local_api_base_url="http://local.invalid",
        normal_upload_limit_bytes=1,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    gateway.upload(chat_id="vault", path=path, media_type=MediaType.IMAGE)
    assert hosts == ["local.invalid"]

    without_local = TelegramMediaGateway(bot_token="token", normal_upload_limit_bytes=1)
    with pytest.raises(TelegramMediaConfigurationError, match="Local Bot API"):
        without_local.upload(chat_id="vault", path=path, media_type=MediaType.IMAGE)
    without_local.close()


def test_gateway_retries_transient_response(tmp_path):
    path = tmp_path / "retry.png"
    path.write_bytes(b"retry")
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        request.read()
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"ok": False, "description": "later"}, request=request)
        return telegram_response(request)

    gateway = TelegramMediaGateway(
        bot_token="token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        backoff_seconds=0.25,
        sleeper=delays.append,
    )
    assert (
        gateway.upload(chat_id="vault", path=path, media_type=MediaType.IMAGE).file_id == "file-42"
    )
    assert attempts == 2
    assert delays == [0.25]


class StubGateway:
    def __init__(self):
        self.calls = 0
        self.closed = False

    def upload(self, **kwargs):
        self.calls += 1
        if kwargs["progress"]:
            kwargs["progress"](10, 10)
        return VaultUpload("99", "vault-file", "vault-unique")

    def close(self):
        self.closed = True


def test_vault_service_is_idempotent_and_keeps_local_file(db, tmp_path):
    pack, asset, path = local_ready_pack(db, tmp_path)
    jobs = enqueue_pack_vault_uploads(db, pack_id=pack.id, vault_chat_id="-100vault")
    assert len(jobs) == 1
    assert (
        enqueue_pack_vault_uploads(db, pack_id=pack.id, vault_chat_id="-100vault")[0].id
        == jobs[0].id
    )
    gateway = StubGateway()
    first = upload_asset_to_vault(
        db,
        asset_id=asset.id,
        vault_chat_id="-100vault",
        media_root=tmp_path,
        gateway=gateway,
    )
    second = upload_asset_to_vault(
        db,
        asset_id=asset.id,
        vault_chat_id="-100vault",
        media_root=tmp_path,
        gateway=gateway,
    )
    assert first.id == second.id
    assert gateway.calls == 1
    assert path.is_file()
    assert asset.status == AssetStatus.VAULTED
    assert asset.telegram_file_id == "vault-file"
    assert asset.telegram_file_unique_id == "vault-unique"
    assert asset.vault_chat_id == "-100vault"
    assert asset.vault_message_id == "99"


def test_worker_persists_upload_progress_and_survives_restart_recovery(db, tmp_path, monkeypatch):
    pack, asset, path = local_ready_pack(db, tmp_path)
    job = enqueue_pack_vault_uploads(db, pack_id=pack.id, vault_chat_id="-100vault")[0]
    db.commit()
    gateway = StubGateway()
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker, "_telegram_gateway", lambda: gateway)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(media_root=tmp_path))
    assert worker.run_once("vault-worker")
    assert db.get(Job, job.id).status == JobStatus.SUCCEEDED
    assert db.get(Job, job.id).payload["bytes_sent"] == 10
    assert db.scalar(select(VaultObject).where(VaultObject.asset_id == asset.id)).verified_at
    assert gateway.closed
    assert path.is_file()

    stale = Job(
        type=JobType.UPLOAD_VAULT,
        payload={"asset_id": asset.id},
        status=JobStatus.RUNNING,
        locked_at=datetime.now(UTC) - timedelta(hours=1),
        lock_owner="dead-worker",
    )
    db.add(stale)
    db.flush()
    assert recover_stale(db, stale_after=timedelta(minutes=15)) == 1
    assert stale.status == JobStatus.QUEUED
    assert stale.lock_owner is None


def test_vault_api_requires_admin_and_configuration(
    client, db, admin_headers, tmp_path, monkeypatch
):
    pack, _, _ = local_ready_pack(db, tmp_path)
    assert client.post(f"/api/v1/vault/packs/{pack.id}").status_code == 401
    monkeypatch.setattr(
        vault_router,
        "get_settings",
        lambda: SimpleNamespace(telegram_vault_chat_id="-100configured"),
    )
    response = client.post(f"/api/v1/vault/packs/{pack.id}", headers=admin_headers)
    assert response.status_code == 200
    assert len(response.json()["jobs"]) == 1
