import re
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(
        default="postgresql+asyncpg://trackit:trackit_dev@localhost:5432/trackit"
    )

    secret_key: str = Field(default="dev_secret_change_me")
    fernet_key: str = Field(default="")
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    api_base_url: str = Field(default="http://localhost:8000")
    mobile_return_scheme: str = Field(default="trackit")

    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")

    gmail_sync_default_lookback_days: int = 30
    gmail_sync_max_messages: int = 200

    itau_statement_pdf_password: str = Field(default="")

    sync_interval_hours: int = Field(default=6)
    sync_scheduler_enabled: bool = Field(default=True)

    # Shared secret for `/internal/cron/*`. On hosts that sleep when idle
    # (Render free) the in-process scheduler can't be trusted, so an external
    # cron (GitHub Actions) calls those endpoints instead. Empty = disabled.
    cron_secret: str = Field(default="")

    resend_api_key: str = Field(default="")
    weekly_summary_from_email: str = Field(default="TrackIt <onboarding@resend.dev>")
    weekly_summary_enabled: bool = Field(default=True)
    weekly_summary_day_of_week: str = Field(default="mon")
    weekly_summary_hour: int = Field(default=8)

    push_alerts_enabled: bool = Field(default=True)
    push_alerts_hour: int = Field(default=8)

    user_timezone: str = Field(default="America/Bogota")

    cors_origins: str = Field(default="*")
    log_level: str = Field(default="INFO")

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        """Accept the plain `postgres://...?sslmode=require` URLs that hosted
        Postgres providers (Neon, Render) hand out: force the asyncpg driver
        and translate libpq's `sslmode` into asyncpg's `ssl` query param."""
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                value = "postgresql+asyncpg://" + value[len(prefix) :]
                break
        value = value.replace("sslmode=", "ssl=")
        # libpq-only param that asyncpg rejects as an unknown server setting.
        value = re.sub(r"[?&]channel_binding=[^&]*", "", value)
        if "?" not in value and "&" in value:
            value = value.replace("&", "?", 1)
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
