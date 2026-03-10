from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class Settings(BaseSettings):
    DB_URL: str
    APP_URL: str
    APP_ENV: str = "local"

    TN_CLIENT_ID: str
    TN_CLIENT_SECRET: str
    TN_OAUTH_BASE: str = "https://www.tiendanube.com"
    TN_API_BASE: str = "https://api.tiendanube.com/2025-03"

    REDIS_URL: str = "redis://localhost:6379/0"

    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    JWT_SECRET: str
    JWT_EXPIRES_SECONDS: int = 3600

    TOKEN_ENCRYPTION_KEY: str
    OAUTH_STATE_SECRET: str

    THUMB_CACHE_DIR: str = "var/thumbs"

    THUMB_SIGNING_SECRET: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="forbid",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def _no_empty_critical_values(self) -> "Settings":
        """
        Fail-fast if critical settings are present but empty/blank.
        BaseSettings enforces presence, but not non-empty strings.
        """
        critical_fields = [
            "DB_URL",
            "APP_URL",
            "TN_CLIENT_ID",
            "TN_CLIENT_SECRET",
            "ADMIN_USERNAME",
            "ADMIN_PASSWORD",
            "JWT_SECRET",
            "TOKEN_ENCRYPTION_KEY",
            "OAUTH_STATE_SECRET",
        ]

        for name in critical_fields:
            value = getattr(self, name, None)
            if isinstance(value, str) and value.strip() == "":
                raise ValueError(f"{name} must not be empty")

        return self


settings = Settings()
