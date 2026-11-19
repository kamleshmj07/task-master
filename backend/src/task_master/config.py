"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from `TASK_MASTER_*` env vars or a `.env` file."""

    model_config = SettingsConfigDict(
        env_prefix="TASK_MASTER_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "Task Master API"
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = ["http://localhost:5173"]
    database_url: SecretStr


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()  # pyright: ignore[reportCallIssue]
