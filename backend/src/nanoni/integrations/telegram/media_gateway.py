from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import httpx


class TelegramMediaError(RuntimeError):
    pass


class TelegramMediaConfigurationError(TelegramMediaError):
    pass


@dataclass(frozen=True)
class VaultUpload:
    message_id: str
    file_id: str
    file_unique_id: str


class _ProgressReader:
    def __init__(self, handle: BinaryIO, callback: Callable[[int, int], None], total: int):
        self.handle = handle
        self.callback = callback
        self.total = total
        self.sent = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self.handle.read(size)
        self.sent += len(chunk)
        self.callback(self.sent, self.total)
        return chunk

    def __getattr__(self, name: str):
        return getattr(self.handle, name)


class TelegramMediaGateway:
    """Streaming boundary for storing local media in a private Telegram vault."""

    def __init__(
        self,
        *,
        bot_token: str,
        api_base_url: str = "https://api.telegram.org",
        local_api_base_url: str = "",
        normal_upload_limit_bytes: int = 50_000_000,
        client: httpx.Client | None = None,
        attempts: int = 3,
        backoff_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not bot_token:
            raise TelegramMediaConfigurationError("Telegram bot token is not configured")
        self.bot_token = bot_token
        self.api_base_url = api_base_url.rstrip("/")
        self.local_api_base_url = local_api_base_url.rstrip("/")
        self.normal_upload_limit_bytes = normal_upload_limit_bytes
        self.client = client or httpx.Client(timeout=httpx.Timeout(30, read=600, write=600))
        self._owns_client = client is None
        self.attempts = max(1, attempts)
        self.backoff_seconds = max(0, backoff_seconds)
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _base_url(self, file_size: int) -> str:
        if file_size <= self.normal_upload_limit_bytes:
            return self.api_base_url
        if not self.local_api_base_url:
            raise TelegramMediaConfigurationError(
                "Telegram Local Bot API URL is required for this file size"
            )
        return self.local_api_base_url

    @staticmethod
    def _method_and_field(media_type: str) -> tuple[str, str]:
        if media_type == "IMAGE":
            return "sendPhoto", "photo"
        if media_type == "VIDEO":
            return "sendVideo", "video"
        if media_type == "GIF":
            return "sendAnimation", "animation"
        return "sendDocument", "document"

    @staticmethod
    def _file_result(result: dict, field: str) -> dict:
        value = result.get(field)
        if field == "photo" and isinstance(value, list) and value:
            value = value[-1]
        if (
            not isinstance(value, dict)
            or not value.get("file_id")
            or not value.get("file_unique_id")
        ):
            raise TelegramMediaError("Telegram response did not contain a reusable file reference")
        return value

    def upload(
        self,
        *,
        chat_id: str,
        path: Path,
        media_type: str,
        mime_type: str | None = None,
        progress: Callable[[int, int], None] | None = None,
    ) -> VaultUpload:
        path = path.resolve()
        if not path.is_file():
            raise TelegramMediaError("Local media file does not exist")
        size = path.stat().st_size
        base_url = self._base_url(size)
        method, field = self._method_and_field(media_type)
        endpoint = f"{base_url}/bot{self.bot_token}/{method}"
        last_error: TelegramMediaError | None = None

        for attempt in range(self.attempts):
            try:
                with path.open("rb") as raw:
                    stream = _ProgressReader(raw, progress, size) if progress else raw
                    response = self.client.post(
                        endpoint,
                        data={"chat_id": chat_id},
                        files={field: (path.name, stream, mime_type or "application/octet-stream")},
                    )
                payload = response.json()
                if not isinstance(payload, dict):
                    raise TelegramMediaError("Telegram returned an invalid response")
                if response.is_success and payload.get("ok") is True:
                    result = payload.get("result")
                    if not isinstance(result, dict) or result.get("message_id") is None:
                        raise TelegramMediaError("Telegram response did not contain a message ID")
                    uploaded = self._file_result(result, field)
                    return VaultUpload(
                        message_id=str(result["message_id"]),
                        file_id=str(uploaded["file_id"]),
                        file_unique_id=str(uploaded["file_unique_id"]),
                    )
                description = payload.get("description", "Telegram upload failed")
                last_error = TelegramMediaError(str(description))
                retry_after = (payload.get("parameters") or {}).get("retry_after")
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable:
                    raise last_error
            except (httpx.TransportError, httpx.TimeoutException, ValueError) as exc:
                last_error = TelegramMediaError("Telegram upload request failed")
                last_error.__cause__ = exc
                retry_after = None
            if attempt + 1 < self.attempts:
                self.sleeper(float(retry_after or self.backoff_seconds * (2**attempt)))

        assert last_error is not None
        raise last_error
