import functools

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven config. Reads from `.env` + environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(default="", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    ingest_token: str | None = Field(default=None, alias="JMI_INGEST_TOKEN")

    @field_validator("database_url")
    @classmethod
    def _require_database_url(cls, value: str) -> str:
        if not value:
            raise ValueError("DATABASE_URL must be set, no default credential fallback")
        return value


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
