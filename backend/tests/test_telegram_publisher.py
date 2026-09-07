from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
import pytest
from sqlalchemy import select

from nanoni.domain.enums import (
    AssetStatus,
    DestinationStatus,
    DestinationType,
    MediaType,
    PackStatus,
    PublicationStatus,
)
from nanoni.domain.models import (
    ContentPack,
    MediaAsset,
    PackItem,
    Publication,
    TelegramDestination,
    Topic,
    VaultObject,
)
from nanoni.domain.services.publishing import (
    PublicationOutcomeUnknownError,
    enqueue_publication,
    publish_publication_job,
)
from nanoni.integrations.telegram.publisher import (
    BotAPITelegramPublisher,
    PublishedMessage,
    PublishMedia,
    TelegramPublisherError,
    TelegramPublisherOutcomeUnknown,
)
from nanoni.jobs import worker


class StubPublisher:
    def __init__(self, *, error: Exception | None = None):
        self.calls = 0
        self.closed = False
        self.error = error

    def publish_pack(self, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        assert kwargs["message_thread_id"] == 77
        assert kwargs["protect_content"] is True
        return PublishedMessage((501, 502), tuple(item.file_id for item in kwargs["media"]))

    def close(self):
        self.closed = True


def ready_publication(db, tmp_path):
    ready = tmp_path / "ready"
    ready.mkdir()
    destination = TelegramDestination(
        name="VIP",
        destination_type=DestinationType.VIP_FORUM,
        telegram_chat_id="-100publish",
        status=DestinationStatus.ACTIVE,
        protected_content=True,
    )
    db.add(destination)
    db.flush()
    topic = Topic(
        destination_id=destination.id,
        name="Topic",
        role="CONTENT",
        message_thread_id=77,
        active=True,
    )
    pack = ContentPack(
        title="Publish pack",
        caption="A caption",
        approved=True,
        status=PackStatus.READY,
    )
    db.add_all([topic, pack])
    db.flush()
    assets = []
    paths = []
    for position, media_type in enumerate((MediaType.IMAGE, MediaType.VIDEO), start=1):
        path = ready / f"asset-{position}.bin"
        path.write_bytes(f"asset-{position}".encode())
        asset = MediaAsset(
            media_type=media_type,
            local_path=str(path),
            telegram_file_id=f"file-{position}",
            telegram_file_unique_id=f"unique-{position}",
            vault_chat_id=destination.telegram_chat_id,
            vault_message_id=str(100 + position),
            status=AssetStatus.VAULTED,
        )
        db.add(asset)
        db.flush()
        db.add_all(
            [
                PackItem(
                    pack_id=pack.id,
                    asset_id=asset.id,
                    position=position,
                    selected=True,
                ),
                VaultObject(
                    asset_id=asset.id,
                    destination_id=destination.id,
                    telegram_message_id=str(100 + position),
                    telegram_file_id=asset.telegram_file_id,
                    verified_at=datetime.now(UTC),
                    metadata_json={"file_unique_id": asset.telegram_file_unique_id},
                ),
            ]
        )
        assets.append(asset)
        paths.append(path)
    db.flush()
    return pack, destination, topic, assets, paths


def test_bot_api_publisher_reuses_file_ids_for_topic_album():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["data"] = parse_qs(request.content.decode())
        return httpx.Response(
            200,
            json={"ok": True, "result": [{"message_id": 41}, {"message_id": 42}]},
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    publisher = BotAPITelegramPublisher(bot_token="token", client=client)
    result = publisher.publish_pack(
        chat_id="-100123",
        media=[PublishMedia("photo-id", "IMAGE"), PublishMedia("video-id", "VIDEO")],
        caption="caption",
        message_thread_id=77,
        protect_content=True,
    )

    assert seen["path"] == "/bottoken/sendMediaGroup"
    assert seen["data"]["chat_id"] == ["-100123"]
    assert seen["data"]["message_thread_id"] == ["77"]
    assert seen["data"]["protect_content"] == ["true"]
    media = json.loads(seen["data"]["media"][0])
    assert media == [
        {"type": "photo", "media": "photo-id", "caption": "caption"},
        {"type": "video", "media": "video-id"},
    ]
    assert result == PublishedMessage((41, 42), ("photo-id", "video-id"))


def test_bot_api_publisher_does_not_replay_ambiguous_transport_failure():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("unknown", request=request)

    publisher = BotAPITelegramPublisher(
        bot_token="token",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        attempts=3,
    )
    with pytest.raises(TelegramPublisherOutcomeUnknown):
        publisher.publish_pack(
            chat_id="chat",
            media=[PublishMedia("file-id", "IMAGE")],
        )
    assert attempts == 1


def test_queue_and_publish_are_idempotent_and_save_references(db, tmp_path):
    pack, destination, topic, assets, paths = ready_publication(db, tmp_path)
    first, first_dispatch = enqueue_publication(
        db,
        pack_id=pack.id,
        destination_id=destination.id,
        topic_id=topic.id,
    )
    second, second_dispatch = enqueue_publication(
        db,
        pack_id=pack.id,
        destination_id=destination.id,
        topic_id=topic.id,
    )
    assert first.id == second.id
    assert first_dispatch.id == second_dispatch.id

    publisher = StubPublisher()
    publication = publish_publication_job(
        db,
        publication_job_id=first.id,
        publisher=publisher,
    )
    repeated = publish_publication_job(
        db,
        publication_job_id=first.id,
        publisher=publisher,
    )

    assert repeated.id == publication.id
    assert publisher.calls == 1
    assert publication.telegram_message_ids == [501, 502]
    assert publication.destination_id == destination.id
    assert publication.topic_id == topic.id
    assert first.status == PublicationStatus.PUBLISHED
    assert all(asset.status == AssetStatus.PUBLISHED for asset in assets)
    assert all(path.is_file() for path in paths)


def test_worker_purges_only_after_confirmed_publication(db, tmp_path, monkeypatch):
    pack, destination, topic, assets, paths = ready_publication(db, tmp_path)
    publication_job, _ = enqueue_publication(
        db,
        pack_id=pack.id,
        destination_id=destination.id,
        topic_id=topic.id,
    )
    db.commit()
    publisher = StubPublisher()
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker, "_telegram_publisher", lambda: publisher)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(media_root=tmp_path))

    assert worker.run_once("publisher-worker")
    publication = db.scalar(
        select(Publication).where(Publication.publication_job_id == publication_job.id)
    )
    assert publication and publication.telegram_message_ids == [501, 502]
    assert publisher.calls == 1 and publisher.closed
    assert all(not path.exists() for path in paths)
    assert all(asset.local_path is None and asset.status == AssetStatus.PURGED for asset in assets)


def test_worker_keeps_local_files_when_telegram_fails(db, tmp_path, monkeypatch):
    pack, destination, topic, assets, paths = ready_publication(db, tmp_path)
    asset_ids = [asset.id for asset in assets]
    publication_job, _ = enqueue_publication(
        db,
        pack_id=pack.id,
        destination_id=destination.id,
        topic_id=topic.id,
    )
    db.commit()
    publisher = StubPublisher(error=TelegramPublisherError("rejected"))
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker, "_telegram_publisher", lambda: publisher)

    assert worker.run_once("publisher-worker")
    assert publication_job.status == PublicationStatus.FAILED
    assert db.scalar(
        select(Publication).where(Publication.publication_job_id == publication_job.id)
    ) is None
    assert publisher.calls == 1 and publisher.closed
    assert all(path.is_file() for path in paths)
    persisted_assets = [db.get(MediaAsset, asset_id) for asset_id in asset_ids]
    assert all(
        asset and asset.local_path is not None and asset.status == AssetStatus.VAULTED
        for asset in persisted_assets
    )


def test_worker_blocks_retry_when_publication_outcome_is_unknown(db, tmp_path, monkeypatch):
    pack, destination, topic, _, paths = ready_publication(db, tmp_path)
    publication_job, dispatch = enqueue_publication(
        db,
        pack_id=pack.id,
        destination_id=destination.id,
        topic_id=topic.id,
    )
    db.commit()
    publisher = StubPublisher(error=TelegramPublisherOutcomeUnknown("timeout"))
    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker, "_telegram_publisher", lambda: publisher)

    assert worker.run_once("publisher-worker")
    assert dispatch.status == "FAILED_FINAL"
    assert db.scalar(
        select(Publication).where(Publication.publication_job_id == publication_job.id)
    ) is None
    assert publication_job.status == PublicationStatus.PUBLISHING
    assert all(path.is_file() for path in paths)

    guard = StubPublisher()
    with pytest.raises(PublicationOutcomeUnknownError):
        publish_publication_job(
            db,
            publication_job_id=publication_job.id,
            publisher=guard,
        )
    assert guard.calls == 0


def test_publication_queue_requires_admin_and_ready_vaulted_pack(
    client, db, admin_headers, tmp_path
):
    pack, destination, topic, _, _ = ready_publication(db, tmp_path)
    url = "/api/v1/publication/queue"
    params = {"pack_id": pack.id, "destination_id": destination.id, "topic_id": topic.id}
    assert client.post(url, params=params).status_code == 401
    response = client.post(url, params=params, headers=admin_headers)
    assert response.status_code == 200, response.text
    repeated = client.post(url, params=params, headers=admin_headers)
    assert repeated.status_code == 200
    assert repeated.json()["id"] == response.json()["id"]
    assert repeated.json()["dispatch_job_id"] == response.json()["dispatch_job_id"]


@pytest.mark.parametrize("count", [0, 11])
def test_publisher_rejects_invalid_album_size(count):
    publisher = BotAPITelegramPublisher(
        bot_token="token",
        client=httpx.Client(transport=httpx.MockTransport(lambda request: None)),
    )
    with pytest.raises(TelegramPublisherError):
        publisher.publish_pack(
            chat_id="chat",
            media=[PublishMedia(f"file-{index}", "IMAGE") for index in range(count)],
        )
