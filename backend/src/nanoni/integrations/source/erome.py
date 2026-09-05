from __future__ import annotations

import hashlib
import ipaddress
import mimetypes
import os
import re
import socket
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup

from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.integrations.source.base import SourceAdapter


class EromeAdapterError(RuntimeError):
    code = "adapter_error"


class UnsupportedEromeUrl(EromeAdapterError):
    code = "unsupported_url"


class UnsafeEromeUrl(EromeAdapterError):
    code = "unsafe_url"


class EromeUnavailable(EromeAdapterError):
    code = "source_unavailable"


class EromeTimeout(EromeAdapterError):
    code = "network_timeout"


class EromeParseError(EromeAdapterError):
    code = "parse_failure"


class EromeMediaUnavailable(EromeAdapterError):
    code = "media_unavailable"


def _resolve_host(host: str) -> Iterable[str]:
    return {entry[4][0] for entry in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}


def _public_address(value: str) -> bool:
    return ipaddress.ip_address(value).is_global


class EromeAdapter(SourceAdapter):
    """Inspect and acquire public Erome albums without bypassing access controls."""

    name = "erome"
    album_hosts = {"erome.com", "www.erome.com"}
    max_redirects = 5

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        resolver: Callable[[str], Iterable[str]] = _resolve_host,
        attempts: int = 3,
        backoff_seconds: float = 0.25,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(30.0, read=120.0),
            follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0 NanoniCollector/0.3"},
        )
        self.resolver = resolver
        self.attempts = max(1, attempts)
        self.backoff_seconds = max(0.0, backoff_seconds)
        self.sleeper = sleeper

    @staticmethod
    def _host_allowed(host: str, *, album: bool) -> bool:
        return host in EromeAdapter.album_hosts if album else (
            host == "erome.com" or host.endswith(".erome.com")
        )

    @staticmethod
    def _album_id(locator: str) -> str:
        segments = [segment for segment in urlparse(locator).path.split("/") if segment]
        if len(segments) == 2 and segments[0] == "a":
            album_id = segments[1]
        elif len(segments) == 1:
            album_id = segments[0]
        else:
            raise UnsupportedEromeUrl("unsupported Erome album URL")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", album_id) or album_id.lower() in {
            "explore",
            "login",
            "register",
        }:
            raise UnsupportedEromeUrl("unsupported Erome album URL")
        return album_id

    def _validate_url(self, locator: str, *, album: bool) -> str:
        parsed = urlparse(locator)
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            port = parsed.port
        except ValueError as exc:
            raise UnsupportedEromeUrl("unsupported Erome URL") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.username
            or parsed.password
            or port not in {None, 80, 443}
            or not self._host_allowed(host, album=album)
        ):
            raise UnsupportedEromeUrl("unsupported Erome URL")
        if album:
            self._album_id(locator)
        try:
            addresses = list(self.resolver(host))
        except OSError as exc:
            raise EromeUnavailable("Erome host could not be resolved") from exc
        try:
            unsafe = not addresses or any(not _public_address(address) for address in addresses)
        except ValueError as exc:
            raise UnsafeEromeUrl("Erome URL resolved to an invalid address") from exc
        if unsafe:
            raise UnsafeEromeUrl("Erome URL resolved to a non-public address")
        return locator

    def _request(self, locator: str, *, album: bool, stream: bool = False) -> httpx.Response:
        current = locator
        for _ in range(self.max_redirects + 1):
            self._validate_url(current, album=album)
            request = self.client.build_request("GET", current)
            response = self.client.send(request, stream=stream, follow_redirects=False)
            if not response.is_redirect:
                return response
            location = response.headers.get("location")
            response.close()
            if not location:
                raise EromeUnavailable("Erome redirect did not include a destination")
            current = urljoin(current, location)
        raise EromeUnavailable("Erome redirect limit exceeded")

    @classmethod
    def parse_album_html(cls, locator: str, html: str) -> MediaManifest:
        album_id = cls._album_id(locator)

        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("meta", property="og:title")
        description_tag = soup.find("meta", property="og:description")
        title = title_tag.get("content") if title_tag else None
        caption = description_tag.get("content") if description_tag else None
        media: list[ManifestAsset] = []
        seen: set[str] = set()

        groups = soup.select("div.media-group")
        if not groups:
            raise EromeParseError("Erome album HTML contained no media groups")

        for group in groups:
            image_node = group.select_one("div.img[data-src], img[data-src]")
            video_node = group.select_one("video source[src], video[src]")
            if image_node:
                node = image_node
                src = str(node.get("data-src"))
                media_type = "IMAGE"
            elif video_node:
                node = video_node
                src = str(node.get("src"))
                media_type = "VIDEO"
            else:
                continue

            source_reference = urljoin(locator, src)
            if source_reference in seen:
                continue
            seen.add(source_reference)
            path_name = Path(unquote(urlparse(source_reference).path)).name
            mime_type, _ = mimetypes.guess_type(path_name)
            parent_video = node if node.name == "video" else node.find_parent("video")
            poster = (
                urljoin(locator, str(parent_video.get("poster")))
                if parent_video and parent_video.get("poster")
                else None
            )
            identity = hashlib.sha256(source_reference.encode()).hexdigest()[:32]
            media.append(
                ManifestAsset(
                    external_item_id=identity,
                    media_type=media_type,
                    source_reference=source_reference,
                    original_filename=(path_name or f"{identity}.bin")[:500],
                    mime_type=mime_type,
                    thumbnail_ref=poster,
                    downloadable=True,
                    metadata={"position": len(media), "poster": poster},
                )
            )

        if not media:
            raise EromeParseError("Erome album HTML contained no supported media")
        return MediaManifest(
            source="erome",
            source_external_id=album_id,
            source_collection_id=album_id,
            source_url=locator,
            title=str(title) if title else None,
            caption=str(caption) if caption else None,
            media=media,
            metadata={"album_id": album_id},
        )

    def inspect(self, locator: str) -> MediaManifest:
        try:
            response = self._request(locator, album=True)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise EromeTimeout("Erome inspection timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise EromeUnavailable(
                f"Erome inspection returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.TransportError as exc:
            raise EromeUnavailable("Erome inspection failed") from exc
        manifest = self.parse_album_html(locator, response.text)
        for item in manifest.media:
            if not item.source_reference:
                raise EromeParseError("Erome media item has no source URL")
            self._validate_url(item.source_reference, album=False)
            if item.thumbnail_ref:
                self._validate_url(item.thumbnail_ref, album=False)
        return manifest

    @staticmethod
    def _retryable(response: httpx.Response) -> bool:
        return response.status_code in {408, 429} or response.status_code >= 500

    def acquire(self, asset_locator: str, destination: Path) -> Path:
        self._validate_url(asset_locator, album=False)
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file():
            return destination

        last_error: Exception | None = None
        for attempt in range(self.attempts):
            partial = destination.with_name(f".{destination.name}.{uuid4().hex}.part")
            response: httpx.Response | None = None
            try:
                response = self._request(asset_locator, album=False, stream=True)
                response.raise_for_status()
                with partial.open("xb") as handle:
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        handle.write(chunk)
                os.replace(partial, destination)
                return destination
            except httpx.TimeoutException as exc:
                last_error = EromeTimeout("Erome media download timed out")
                last_error.__cause__ = exc
            except httpx.HTTPStatusError as exc:
                if not self._retryable(exc.response):
                    raise EromeMediaUnavailable(
                        f"Erome media returned HTTP {exc.response.status_code}"
                    ) from exc
                last_error = EromeMediaUnavailable(
                    f"Erome media returned HTTP {exc.response.status_code}"
                )
            except httpx.TransportError as exc:
                last_error = EromeMediaUnavailable("Erome media download failed")
                last_error.__cause__ = exc
            finally:
                if response is not None:
                    response.close()
                partial.unlink(missing_ok=True)
            if attempt + 1 < self.attempts:
                self.sleeper(self.backoff_seconds * (2**attempt))
        assert last_error is not None
        raise last_error
