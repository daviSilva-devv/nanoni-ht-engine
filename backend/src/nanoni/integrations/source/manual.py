from pathlib import Path

from nanoni.domain.schemas import ManifestAsset, MediaManifest
from nanoni.integrations.source.base import SourceAdapter


class ManualUploadAdapter(SourceAdapter):
    name = "manual"

    def inspect(self, locator: str) -> MediaManifest:
        path = Path(locator)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(locator)
        media_type = (
            "VIDEO" if path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"} else "IMAGE"
        )
        return MediaManifest(
            source="manual",
            source_item_id=str(path.resolve()),
            source_url=None,
            title=path.name,
            media=[
                ManifestAsset(
                    source_locator=str(path.resolve()),
                    media_type=media_type,
                    file_size=path.stat().st_size,
                )
            ],
        )

    def acquire(self, asset_locator: str, destination: Path) -> Path:
        source = Path(asset_locator)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return destination
