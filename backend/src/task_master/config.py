"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import PositiveInt, SecretStr, StringConstraints, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LENGTH = 32


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
    # Path every route is served under, e.g. "/api" when the web app and the
    # API share one address (Vercel). Empty: routes start at the root.
    api_prefix: Annotated[str, StringConstraints(pattern=r"^(/[a-z0-9-]+)*$")] = ""
    database_url: SecretStr
    # True behind a connection pooler such as Neon's (serverless hosting):
    # no pool of our own and no prepared-statement cache.
    database_pooled: bool = False
    auth_secret: SecretStr
    access_token_lifetime_seconds: int = 15 * 60
    refresh_token_lifetime_days: int = 30
    auth_rate_limit: str = "5/minute"
    # Every other endpoint, per session (or per IP when signed out).
    api_rate_limit: str = "300/minute"
    api_write_rate_limit: str = "120/minute"
    # All requests from one IP, whatever token they carry. Higher than the
    # per-session budget so people sharing a network are not blocked.
    api_ip_rate_limit: str = "600/minute"
    # Proxies whose X-Forwarded-For is trusted, e.g. the host's load
    # balancer. Empty: the connecting address is the client.
    trusted_proxies: list[str] = []
    login_free_failures: PositiveInt = 5
    login_base_lock_seconds: PositiveInt = 60
    login_max_lock_seconds: PositiveInt = 15 * 60
    login_ip_failures: PositiveInt = 20
    login_ip_window_seconds: PositiveInt = 15 * 60
    completed_task_retention_days: PositiveInt = 90

    @model_validator(mode="after")
    def check_production(self) -> Self:
        """Refuse to run production with development defaults."""
        if self.environment != "production":
            return self
        if not self.cors_origins or any(
            not origin.startswith("https://") for origin in self.cors_origins
        ):
            raise ValueError("Production cors_origins must be HTTPS origins")
        if len(self.auth_secret.get_secret_value()) < MIN_SECRET_LENGTH:
            raise ValueError(
                f"Production auth_secret needs at least {MIN_SECRET_LENGTH} characters"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()  # pyright: ignore[reportCallIssue]
