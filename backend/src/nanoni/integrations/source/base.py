from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from nanoni.domain.schemas import MediaManifest


class SourceAdapter(ABC):
    name: str

    @abstractmethod
    def inspect(self, locator: str) -> MediaManifest: ...

    def search(self, query: str, filters: dict | None = None) -> list[MediaManifest]:
        raise NotImplementedError

    def list_collection(self, locator: str) -> list[MediaManifest]:
        return [self.inspect(locator)]

    @abstractmethod
    def acquire(self, asset_locator: str, destination: Path) -> Path: ...
