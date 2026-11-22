"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import PositiveInt, SecretStr
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
    auth_secret: SecretStr
    access_token_lifetime_seconds: int = 15 * 60
    refresh_token_lifetime_days: int = 30
    auth_rate_limit: str = "5/minute"
    login_free_failures: PositiveInt = 5
    login_base_lock_seconds: PositiveInt = 60
    login_max_lock_seconds: PositiveInt = 15 * 60
    login_ip_failures: PositiveInt = 20
    login_ip_window_seconds: PositiveInt = 15 * 60
    completed_task_retention_days: PositiveInt = 90


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()  # pyright: ignore[reportCallIssue]
