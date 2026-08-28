from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.integrations.source.base import SourceAdapter


class EromeAdapter(SourceAdapter):
    """Public-album adapter.

    It inspects the album first and returns a MediaManifest. Acquisition happens only
    for assets selected by the operator. The adapter intentionally does not handle
    private/paywalled/restricted material or attempt to bypass access controls.
    """

    name = "erome"
    allowed_hosts = {"www.erome.com", "erome.com"}

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, read=120.0),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 NanoniCollector/0.2"},
        )

    def _validate(self, locator: str) -> None:
        parsed = urlparse(locator)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in self.allowed_hosts:
            raise ValueError("unsupported Erome locator")

    @staticmethod
    def parse_album_html(locator: str, html: str) -> MediaManifest:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("meta", property="og:title")
        title = title_tag.get("content") if title_tag else None
        media: list[ManifestAsset] = []
        seen: set[str] = set()
        position = 0
        for node in soup.find_all(["source", "div"]):
            src = None
            media_type = None
            if node.name == "source" and node.get("src"):
                src = node.get("src")
                media_type = "VIDEO"
            elif node.name == "div" and "img" in (node.get("class") or []) and node.get("data-src"):
                src = node.get("data-src")
                media_type = "IMAGE"
            if not src or src in seen:
                continue
            seen.add(src)
            media.append(
                ManifestAsset(
                    source_locator=src,
                    media_type=media_type,
                    downloadable=True,
                    metadata={"position": position},
                )
            )
            position += 1
        source_item_id = urlparse(locator).path.strip("/") or locator
        return MediaManifest(
            source="erome",
            source_collection_id=source_item_id,
            source_item_id=source_item_id,
            source_url=locator,
            title=title,
            media=media,
        )

    def inspect(self, locator: str) -> MediaManifest:
        self._validate(locator)
        response = self.client.get(locator)
        response.raise_for_status()
        return self.parse_album_html(locator, response.text)

    def acquire(self, asset_locator: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.client.stream("GET", asset_locator) as response:
            response.raise_for_status()
            with destination.open("wb") as handle:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    handle.write(chunk)
        return destination
