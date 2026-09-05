from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import select

from nanoni.api.routers import content as content_router
from nanoni.domain.enums import AssetStatus, DuplicateClassification, JobStatus
from nanoni.domain.models import ContentCandidate, ContentPack, Job, MediaAsset, PackItem
from nanoni.domain.services.content import pack_read, set_pack_selection
from nanoni.integrations.source.erome import (
    EromeAdapter,
    EromeMediaUnavailable,
    EromeParseError,
    EromeTimeout,
    UnsafeEromeUrl,
    UnsupportedEromeUrl,
)
from nanoni.integrations.source.erome_service import (
    acquire_pack_item,
    enqueue_selected_acquisition,
    inspect_and_import,
)
from nanoni.jobs import worker

FIXTURE = Path(__file__).parent / "fixtures" / "erome_album.html"
PUBLIC_DNS = lambda host: ["93.184.216.34"]  # noqa: E731


def adapter_for(handler, **kwargs) -> EromeAdapter:
    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    options = {"backoff_seconds": 0, "sleeper": lambda _: None, **kwargs}
    return EromeAdapter(client, resolver=PUBLIC_DNS, **options)


def fixture_handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "www.erome.com":
        return httpx.Response(200, text=FIXTURE.read_text(encoding="utf8"), request=request)
    return httpx.Response(200, content=b"media-bytes", request=request)


def test_fixture_parser_preserves_mixed_album_order_and_metadata():
    manifest = EromeAdapter.parse_album_html(
        "https://www.erome.com/fixture-album", FIXTURE.read_text(encoding="utf8")
    )
    assert manifest.source == "erome"
    assert manifest.source_item_id == "fixture-album"
    assert manifest.title == "Fixture mixed album"
    assert len(manifest.media) == 4
    assert [item.media_type for item in manifest.media] == ["IMAGE", "VIDEO", "IMAGE", "VIDEO"]
    assert [item.metadata["position"] for item in manifest.media] == [0, 1, 2, 3]
    assert manifest.media[1].thumbnail_ref.endswith("poster-02.png")


def test_inspect_fetches_only_html_and_rejects_empty_parser_result():
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, text=FIXTURE.read_text(encoding="utf8"), request=request)

    manifest = adapter_for(handler).inspect("https://www.erome.com/fixture-album")
    assert len(manifest.media) == 4
    assert requests == ["https://www.erome.com/fixture-album"]
    with pytest.raises(EromeParseError, match="no media"):
        EromeAdapter.parse_album_html("https://www.erome.com/broken", "<html></html>")


def test_inspect_imports_one_candidate_and_one_pack(db):
    outcome = inspect_and_import(
        db, "https://www.erome.com/fixture-album", adapter_for(fixture_handler)
    )
    assert db.scalar(select(ContentCandidate).where(ContentCandidate.id == outcome.candidate.id))
    assert db.scalar(select(ContentPack).where(ContentPack.id == outcome.pack.id))
    assert len(pack_read(db, outcome.pack.id).items) == 4


def test_selective_acquisition_queues_and_downloads_only_selected_items(db, tmp_path):
    adapter = adapter_for(fixture_handler)
    outcome = inspect_and_import(db, "https://www.erome.com/selective", adapter)
    set_pack_selection(db, outcome.pack.id, [1, 3])

    jobs = enqueue_selected_acquisition(db, outcome.pack.id)
    assert len(jobs) == 2
    selected_ids = {str(job.payload["pack_item_id"]) for job in jobs}
    assert selected_ids == {
        item.id for item in pack_read(db, outcome.pack.id).items if item.selected
    }
    assert [job.id for job in enqueue_selected_acquisition(db, outcome.pack.id)] == [
        job.id for job in jobs
    ]

    for job in jobs:
        acquire_pack_item(
            db,
            pack_item_id=str(job.payload["pack_item_id"]),
            media_root=tmp_path,
            adapter=adapter,
        )
        acquire_pack_item(
            db,
            pack_item_id=str(job.payload["pack_item_id"]),
            media_root=tmp_path,
            adapter=adapter_for(lambda request: pytest.fail("idempotent retry downloaded again")),
        )
    items = pack_read(db, outcome.pack.id).items
    assert len(items) == 4
    assert all(item.asset.status == AssetStatus.LOCAL_READY for item in items if item.selected)
    assert all(item.asset.status == AssetStatus.DISCOVERED for item in items if not item.selected)
    assert all(item.asset.sha256 == hashlib.sha256(b"media-bytes").hexdigest() for item in items if item.selected)


class RecordingStream(httpx.SyncByteStream):
    def __init__(self, chunks, *, error=None):
        self.chunks = chunks
        self.error = error
        self.yields = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.yields += 1
            yield chunk
        if self.error:
            raise self.error


def test_download_is_streamed_and_retries_transient_status(tmp_path):
    attempts = 0
    delays: list[float] = []
    stream = RecordingStream([b"one", b"two", b"three"])

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, request=request)
        return httpx.Response(200, stream=stream, request=request)

    destination = tmp_path / "media.bin"
    adapter_for(handler, backoff_seconds=0.5, sleeper=delays.append).acquire(
        "https://v.erome.com/media.bin", destination
    )
    assert destination.read_bytes() == b"onetwothree"
    assert attempts == 3
    assert delays == [0.5, 1.0]
    assert stream.yields == 3
    assert not list(tmp_path.glob("*.part"))


def test_timeout_exhausts_retries_without_publishing_partial_file(tmp_path):
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        timeout = httpx.ReadTimeout("slow", request=request)
        return httpx.Response(
            200,
            stream=RecordingStream([b"partial"], error=timeout),
            request=request,
        )

    destination = tmp_path / "never-ready.bin"
    with pytest.raises(EromeTimeout):
        adapter_for(handler, attempts=2).acquire("https://v.erome.com/slow.bin", destination)
    assert attempts == 2
    assert not destination.exists()
    assert not list(tmp_path.iterdir())


def test_media_404_is_final_and_does_not_retry(tmp_path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, request=request)

    with pytest.raises(EromeMediaUnavailable, match="404"):
        adapter_for(handler).acquire("https://v.erome.com/missing.mp4", tmp_path / "missing.mp4")
    assert calls == 1


@pytest.mark.parametrize(
    "locator",
    [
        "file:///etc/passwd",
        "http://localhost/album",
        "http://127.0.0.1/album",
        "http://10.0.0.1/album",
        "https://erome.com.evil.test/album",
        "https://www.erome.com/explore",
    ],
)
def test_unsupported_or_local_album_urls_are_blocked(locator):
    with pytest.raises(UnsupportedEromeUrl):
        adapter_for(fixture_handler).inspect(locator)


def test_private_dns_and_unsafe_redirect_are_blocked():
    private = EromeAdapter(
        httpx.Client(transport=httpx.MockTransport(fixture_handler)),
        resolver=lambda host: ["192.168.1.10"],
    )
    with pytest.raises(UnsafeEromeUrl):
        private.inspect("https://www.erome.com/album")

    def redirect(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"}, request=request)

    with pytest.raises(UnsupportedEromeUrl):
        adapter_for(redirect).inspect("https://www.erome.com/album")


def test_sha_dedupe_reuses_blob_and_source_identity_is_idempotent(db, tmp_path):
    def distinct_item_handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.erome.com":
            album_id = request.url.path.strip("/")
            html = FIXTURE.read_text(encoding="utf8").replace("/fixture/", f"/{album_id}/")
            return httpx.Response(200, text=html, request=request)
        return httpx.Response(200, content=b"same-physical-media", request=request)

    adapter = adapter_for(distinct_item_handler)
    first = inspect_and_import(db, "https://www.erome.com/first", adapter)
    first_item = pack_read(db, first.pack.id).items[0]
    first_asset = acquire_pack_item(
        db, pack_item_id=first_item.id, media_root=tmp_path, adapter=adapter
    )

    second = inspect_and_import(db, "https://www.erome.com/second", adapter)
    second_item = pack_read(db, second.pack.id).items[0]
    second_asset = acquire_pack_item(
        db, pack_item_id=second_item.id, media_root=tmp_path, adapter=adapter
    )
    assert second_asset.local_path == first_asset.local_path
    assert second.candidate.duplicate_classification == DuplicateClassification.SAME_SHA256
    assert len(list((tmp_path / "processing").iterdir())) == 1

    repeated = inspect_and_import(db, "https://www.erome.com/first", adapter)
    assert repeated.candidate.id == first.candidate.id
    assert repeated.classification == DuplicateClassification.SAME_SOURCE_ITEM


def test_api_requires_admin_and_reuses_phase2_pack_contract(client, db, admin_headers):
    adapter = adapter_for(fixture_handler)
    client.app.dependency_overrides[content_router.get_erome_adapter] = lambda: adapter
    assert client.post("/api/v1/content/erome/inspect", json={"locator": "x"}).status_code == 401

    imported = client.post(
        "/api/v1/content/erome/import",
        headers=admin_headers,
        json={"locator": "https://www.erome.com/api-album"},
    )
    assert imported.status_code == 201
    pack_id = imported.json()["pack_id"]
    pack = client.get(f"/api/v1/content/packs/{pack_id}", headers=admin_headers)
    assert pack.status_code == 200
    assert len(pack.json()["items"]) == 4

    selected = client.put(
        f"/api/v1/content/packs/{pack_id}/selection",
        headers=admin_headers,
        json={"selected_positions": [1, 4]},
    )
    assert selected.status_code == 200
    queued = client.post(
        f"/api/v1/content/packs/{pack_id}/acquire-selected", headers=admin_headers
    )
    assert queued.status_code == 200
    assert len(queued.json()["jobs"]) == 2
    assert all(job["status"] == JobStatus.QUEUED for job in queued.json()["jobs"])


def test_unselected_stale_job_does_not_download(db, tmp_path):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return fixture_handler(request)

    adapter = adapter_for(handler)
    outcome = inspect_and_import(db, "https://www.erome.com/stale", adapter)
    item = db.scalar(select(PackItem).where(PackItem.pack_id == outcome.pack.id))
    item.selected = False
    asset = acquire_pack_item(db, pack_item_id=item.id, media_root=tmp_path, adapter=adapter)
    assert asset.status == AssetStatus.DISCOVERED
    assert calls == 1  # album inspect only


def test_acquire_media_job_handler_persists_success(db, tmp_path, monkeypatch):
    adapter = adapter_for(fixture_handler)
    outcome = inspect_and_import(db, "https://www.erome.com/job", adapter)
    set_pack_selection(db, outcome.pack.id, [1])
    job = enqueue_selected_acquisition(db, outcome.pack.id)[0]
    db.commit()

    monkeypatch.setattr(worker, "SessionLocal", lambda: db)
    monkeypatch.setattr(worker, "EromeAdapter", lambda: adapter)
    monkeypatch.setattr(worker, "get_settings", lambda: SimpleNamespace(media_root=tmp_path))
    assert worker.run_once("phase3a-test-worker")

    persisted_job = db.get(Job, job.id)
    item = db.get(PackItem, str(job.payload["pack_item_id"]))
    asset = db.get(MediaAsset, item.asset_id)
    assert persisted_job.status == JobStatus.SUCCEEDED
    assert asset.status == AssetStatus.LOCAL_READY
