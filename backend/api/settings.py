"""App settings from environment variables (backend/.env)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND / ".env", extra="ignore")

    database_url: str | None = None

    # Auth: real Auth0 when AUTH0_DOMAIN and AUTH0_AUDIENCE are set; otherwise dev tokens signed with AUTH_DEV_SECRET.
    auth0_domain: str | None = None
    auth0_audience: str | None = None
    auth_dev_secret: str | None = None

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    gemini_fallback_model: str = "gemini-3.1-flash-lite"

    cors_origins: str = "http://localhost:3000"
    timezone: str = "Europe/London"
    alert_daily_limit: int = 3
    scheduler_enabled: bool = False

    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    vapid_subject: str = "mailto:team@example.com"

    @property
    def auth_mode(self) -> str:
        if self.auth0_domain and self.auth0_audience:
            return "auth0"
        if self.auth_dev_secret:
            return "dev"
        return "none"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
