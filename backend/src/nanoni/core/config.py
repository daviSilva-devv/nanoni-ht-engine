from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NANONI_",
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
        case_sensitive=False,
    )

    project_root: Path = PROJECT_ROOT
    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "sqlite:///./nanoni.db"
    log_level: str = "INFO"
    admin_token: str = "change-me-local"
    media_root: Path = Path("runtime/media")
    helper_shared_secret: str = "change-me-helper"
    payment_provider: str = "mock"
    external_checkout_base_url: str = "http://localhost:3000/checkout"
    bravopay_api_base_url: str = "https://bravopay.club/api/v1"
    bravopay_api_key: str = ""
    bravopay_webhook_secret: str = ""
    bravopay_pix_expires_in: int = 3600
    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""
    telegram_api_base_url: str = "https://api.telegram.org"
    telegram_local_api_base_url: str = ""
    telegram_vault_chat_id: str = ""
    telegram_bot_api_max_upload_bytes: int = 50_000_000

    @model_validator(mode="after")
    def resolve_project_paths(self) -> "Settings":
        self.project_root = self.project_root.resolve()
        if not self.media_root.is_absolute():
            self.media_root = (self.project_root / self.media_root).resolve()
        if self.database_url.startswith("sqlite:///"):
            sqlite_path = self.database_url.removeprefix("sqlite:///")
            if sqlite_path != ":memory:" and not Path(sqlite_path).is_absolute():
                database_path = (self.project_root / sqlite_path).resolve().as_posix()
                self.database_url = f"sqlite:///{database_path}"
        return self

    @property
    def is_production(self) -> bool:
        return self.env == "prod"

    @model_validator(mode="after")
    def validate_payment_configuration(self) -> "Settings":
        if self.payment_provider.lower() == "bravopay" and not self.bravopay_api_key:
            raise ValueError("NANONI_BRAVOPAY_API_KEY is required for the BravoPay provider")
        if not 60 <= self.bravopay_pix_expires_in <= 86400:
            raise ValueError("NANONI_BRAVOPAY_PIX_EXPIRES_IN must be between 60 and 86400")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
