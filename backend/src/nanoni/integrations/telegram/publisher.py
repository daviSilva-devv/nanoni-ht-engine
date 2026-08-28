from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PublishedMessage:
    message_ids: tuple[int, ...]
    file_ids: tuple[str, ...] = ()


class TelegramPublisher(ABC):
    """Boundary around Bot API / local Bot API server.

    A real implementation is added in the publisher phase. Keeping this boundary now
    prevents content, scheduling and business code from importing Telegram SDK calls.
    """

    @abstractmethod
    def publish_pack(
        self,
        *,
        chat_id: str,
        files: list[Path],
        caption: str | None = None,
        message_thread_id: int | None = None,
        protect_content: bool = False,
    ) -> PublishedMessage: ...

    @abstractmethod
    def approve_join_request(self, *, chat_id: str, telegram_user_id: str) -> None: ...

    @abstractmethod
    def remove_member(self, *, chat_id: str, telegram_user_id: str) -> None: ...
