import functools

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggingSettings(BaseSettings):
    """Observability config. Deliberately free of DB/credential fields so it can
    be built for `--help` and other DB-less paths without DATABASE_URL (#58)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")


class Settings(LoggingSettings):
    """Environment-driven config. Reads from `.env` + environment variables."""

    database_url: str = Field(default="", alias="DATABASE_URL")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    ingest_token: str | None = Field(default=None, alias="JMI_INGEST_TOKEN")
    achievements_vault_path: str | None = Field(default=None, alias="ACHIEVEMENTS_VAULT_PATH")

    @field_validator("database_url")
    @classmethod
    def _require_database_url(cls, value: str) -> str:
        if not value:
            raise ValueError("DATABASE_URL must be set, no default credential fallback")
        return value


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@functools.lru_cache(maxsize=1)
def get_logging_settings() -> LoggingSettings:
    return LoggingSettings()
