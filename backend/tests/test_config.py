"""Tests for settings loading."""

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from task_master.config import Settings


class EnvOnlySettings(Settings):
    """Settings that ignore any local `.env` file, so tests see only env vars."""

    model_config = SettingsConfigDict(env_file=None)


def load_settings() -> Settings:
    """Load settings from env vars only."""
    return EnvOnlySettings()  # pyright: ignore[reportCallIssue]


@pytest.fixture(autouse=True)
def database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide the required database URL."""
    monkeypatch.setenv("TASK_MASTER_DATABASE_URL", "postgresql+asyncpg://u:p@h/db")


class TestSettings:
    def test_defaults_to_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TASK_MASTER_ENVIRONMENT", raising=False)

        assert load_settings().environment == "development"

    def test_reads_prefixed_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_ENVIRONMENT", "production")

        assert load_settings().environment == "production"

    def test_parses_cors_origins_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_CORS_ORIGINS", '["https://a.com"]')

        assert load_settings().cors_origins == ["https://a.com"]

    def test_rejects_unknown_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_ENVIRONMENT", "staging")

        with pytest.raises(ValidationError):
            load_settings()

    def test_requires_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TASK_MASTER_DATABASE_URL")

        with pytest.raises(ValidationError):
            load_settings()

    def test_hides_database_url_in_repr(self) -> None:
        assert "u:p@h" not in repr(load_settings())
