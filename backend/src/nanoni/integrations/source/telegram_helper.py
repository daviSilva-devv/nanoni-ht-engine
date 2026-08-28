from pathlib import Path

from nanoni.domain.schemas import MediaManifest
from nanoni.integrations.source.base import SourceAdapter


class TelegramHelperAdapter(SourceAdapter):
    """Contract for assisted imports produced by the local browser helper.

    The helper may send post metadata and a local file path obtained through a user-
    authorized route. This adapter does not implement bypass of Telegram protected
    content controls.
    """

    name = "telegram-helper"

    def inspect(self, locator: str) -> MediaManifest:
        raise NotImplementedError(
            "helper pushes manifests to the local bridge; it is not remote-inspected"
        )

    def acquire(self, asset_locator: str, destination: Path) -> Path:
        source = Path(asset_locator)
        if not source.exists():
            raise FileNotFoundError(asset_locator)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return destination
