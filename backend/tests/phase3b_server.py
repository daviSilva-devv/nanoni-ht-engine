from __future__ import annotations

import atexit
import base64
import threading
from collections import Counter
from pathlib import Path
from time import sleep

import httpx

from nanoni.api.main import create_app
from nanoni.api.routers.content import get_erome_adapter
from nanoni.integrations.source.erome import EromeAdapter
from nanoni.jobs import worker

FIXTURE = Path(__file__).parent / "fixtures" / "erome_album.html"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZbmoAAAAASUVORK5CYII="
)
WEBM = b"\x1aE\xdf\xa3phase3b-deterministic-webm"
COUNTS: Counter[str] = Counter()
STOP = threading.Event()


def mock_erome(request: httpx.Request) -> httpx.Response:
    if request.url.host == "www.erome.com":
        COUNTS["html"] += 1
        album_id = request.url.path.rstrip("/").split("/")[-1]
        html = FIXTURE.read_text(encoding="utf8").replace("/fixture/", f"/{album_id}/")
        return httpx.Response(200, text=html, request=request)

    COUNTS["media"] += 1
    key = str(request.url)
    COUNTS[key] += 1
    if request.url.path.endswith("video-02.webm") and COUNTS[key] == 1:
        return httpx.Response(503, request=request)
    if request.url.path.endswith(".png"):
        return httpx.Response(200, content=PNG, headers={"Content-Type": "image/png"}, request=request)
    return httpx.Response(200, content=WEBM, headers={"Content-Type": "video/webm"}, request=request)


def make_adapter() -> EromeAdapter:
    client = httpx.Client(transport=httpx.MockTransport(mock_erome), follow_redirects=False)
    return EromeAdapter(
        client,
        resolver=lambda host: ["93.184.216.34"],
        backoff_seconds=0.01,
    )


def adapter_dependency():
    adapter = make_adapter()
    try:
        yield adapter
    finally:
        adapter.client.close()


def worker_loop() -> None:
    while not STOP.is_set():
        if not worker.run_once("phase3b-e2e-worker"):
            sleep(0.05)


app = create_app()
app.dependency_overrides[get_erome_adapter] = adapter_dependency
worker.EromeAdapter = make_adapter
threading.Thread(target=worker_loop, name="phase3b-worker", daemon=True).start()
atexit.register(STOP.set)


@app.get("/__test__/network-status")
def network_status() -> dict[str, int]:
    return {"html": COUNTS["html"], "media": COUNTS["media"]}
