from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

import httpx


class TelegramPublisherError(RuntimeError):
    pass


class TelegramPublisherConfigurationError(TelegramPublisherError):
    pass


class TelegramPublisherOutcomeUnknown(TelegramPublisherError):
    """The request may have reached Telegram and must not be replayed automatically."""


@dataclass(frozen=True)
class PublishMedia:
    file_id: str
    media_type: str


@dataclass(frozen=True)
class PublishedMessage:
    message_ids: tuple[int, ...]
    file_ids: tuple[str, ...] = ()


class TelegramPublisher(ABC):
    """Boundary around Telegram publishing and membership operations."""

    @abstractmethod
    def publish_pack(
        self,
        *,
        chat_id: str,
        media: list[PublishMedia],
        caption: str | None = None,
        message_thread_id: int | None = None,
        protect_content: bool = False,
    ) -> PublishedMessage: ...

    @abstractmethod
    def approve_join_request(self, *, chat_id: str, telegram_user_id: str) -> None: ...

    def decline_join_request(self, *, chat_id: str, telegram_user_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_member(self, *, chat_id: str, telegram_user_id: str) -> None: ...


class BotAPITelegramPublisher(TelegramPublisher):
    def __init__(
        self,
        *,
        bot_token: str,
        api_base_url: str = "https://api.telegram.org",
        client: httpx.Client | None = None,
        attempts: int = 3,
        backoff_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not bot_token:
            raise TelegramPublisherConfigurationError("Telegram bot token is not configured")
        self.bot_token = bot_token
        self.api_base_url = api_base_url.rstrip("/")
        self.client = client or httpx.Client(timeout=httpx.Timeout(30, read=120, write=120))
        self._owns_client = client is None
        self.attempts = max(1, attempts)
        self.backoff_seconds = max(0, backoff_seconds)
        self.sleeper = sleeper

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _post(self, method: str, data: dict[str, object]) -> object:
        endpoint = f"{self.api_base_url}/bot{self.bot_token}/{method}"
        last_error: TelegramPublisherError | None = None
        for attempt in range(self.attempts):
            retry_after = None
            try:
                response = self.client.post(endpoint, data=data)
                payload = response.json()
                if not isinstance(payload, dict):
                    raise TelegramPublisherError("Telegram returned an invalid response")
                if response.is_success and payload.get("ok") is True:
                    return payload.get("result")
                last_error = TelegramPublisherError(
                    str(payload.get("description", "Telegram operation failed"))
                )
                parameters = payload.get("parameters")
                if isinstance(parameters, dict):
                    retry_after = parameters.get("retry_after")
                if response.status_code >= 500:
                    raise TelegramPublisherOutcomeUnknown(
                        "Telegram returned an ambiguous server error"
                    )
                if response.status_code != 429:
                    raise last_error
            except (httpx.TransportError, httpx.TimeoutException, ValueError) as exc:
                raise TelegramPublisherOutcomeUnknown(
                    "Telegram publication outcome is unknown"
                ) from exc
            if attempt + 1 < self.attempts:
                self.sleeper(float(retry_after or self.backoff_seconds * (2**attempt)))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _single_method_and_field(media_type: str) -> tuple[str, str]:
        if media_type == "IMAGE":
            return "sendPhoto", "photo"
        if media_type == "VIDEO":
            return "sendVideo", "video"
        if media_type == "GIF":
            return "sendAnimation", "animation"
        raise TelegramPublisherError(f"unsupported media type: {media_type}")

    def publish_pack(
        self,
        *,
        chat_id: str,
        media: list[PublishMedia],
        caption: str | None = None,
        message_thread_id: int | None = None,
        protect_content: bool = False,
    ) -> PublishedMessage:
        if not media:
            raise TelegramPublisherError("publication pack has no media")
        common: dict[str, object] = {
            "chat_id": chat_id,
            "protect_content": json.dumps(protect_content),
        }
        if message_thread_id is not None:
            common["message_thread_id"] = message_thread_id

        if len(media) == 1:
            item = media[0]
            method, field = self._single_method_and_field(item.media_type)
            data = {**common, field: item.file_id}
            if caption:
                data["caption"] = caption
            result = self._post(method, data)
            if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
                raise TelegramPublisherError("Telegram response did not contain a message ID")
            return PublishedMessage((result["message_id"],), (item.file_id,))

        if len(media) > 10:
            raise TelegramPublisherError("Telegram media groups support at most 10 items")
        if any(item.media_type not in {"IMAGE", "VIDEO"} for item in media):
            raise TelegramPublisherError("multi-item packs support IMAGE and VIDEO assets")
        payload_media = []
        for index, item in enumerate(media):
            entry = {
                "type": "photo" if item.media_type == "IMAGE" else "video",
                "media": item.file_id,
            }
            if index == 0 and caption:
                entry["caption"] = caption
            payload_media.append(entry)
        result = self._post("sendMediaGroup", {**common, "media": json.dumps(payload_media)})
        if (
            not isinstance(result, list)
            or len(result) != len(media)
            or any(
                not isinstance(row, dict) or not isinstance(row.get("message_id"), int)
                for row in result
            )
        ):
            raise TelegramPublisherError("Telegram response did not contain all message IDs")
        return PublishedMessage(
            tuple(row["message_id"] for row in result),
            tuple(item.file_id for item in media),
        )

    def approve_join_request(self, *, chat_id: str, telegram_user_id: str) -> None:
        result = self._post(
            "approveChatJoinRequest",
            {"chat_id": chat_id, "user_id": telegram_user_id},
        )
        if result is not True:
            raise TelegramPublisherError("Telegram did not confirm join request approval")

    def decline_join_request(self, *, chat_id: str, telegram_user_id: str) -> None:
        result = self._post(
            "declineChatJoinRequest",
            {"chat_id": chat_id, "user_id": telegram_user_id},
        )
        if result is not True:
            raise TelegramPublisherError("Telegram did not confirm join request decline")

    def remove_member(self, *, chat_id: str, telegram_user_id: str) -> None:
        result = self._post(
            "banChatMember",
            {"chat_id": chat_id, "user_id": telegram_user_id},
        )
        if result is not True:
            raise TelegramPublisherError("Telegram did not confirm member removal")
