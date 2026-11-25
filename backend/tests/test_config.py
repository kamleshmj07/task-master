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
    monkeypatch.setenv("TASK_MASTER_AUTH_SECRET", "s3cret-value")


class TestSettings:
    def test_defaults_to_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TASK_MASTER_ENVIRONMENT", raising=False)

        assert load_settings().environment == "development"

    def test_reads_prefixed_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_ENVIRONMENT", "test")

        assert load_settings().environment == "test"

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

    def test_hides_auth_secret_in_repr(self) -> None:
        assert "s3cret-value" not in repr(load_settings())

    def test_requires_auth_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TASK_MASTER_AUTH_SECRET")

        with pytest.raises(ValidationError):
            load_settings()


class TestApiPrefix:
    def test_defaults_to_no_prefix(self) -> None:
        assert load_settings().api_prefix == ""

    @pytest.mark.parametrize("prefix", ["/api", "/v1/api"])
    def test_accepts_a_path(self, monkeypatch: pytest.MonkeyPatch, prefix: str) -> None:
        monkeypatch.setenv("TASK_MASTER_API_PREFIX", prefix)

        assert load_settings().api_prefix == prefix

    @pytest.mark.parametrize("prefix", ["api", "/api/", "/", "/API", "/a b"])
    def test_rejects_anything_else(
        self, monkeypatch: pytest.MonkeyPatch, prefix: str
    ) -> None:
        monkeypatch.setenv("TASK_MASTER_API_PREFIX", prefix)

        with pytest.raises(ValidationError):
            load_settings()


class TestDatabasePooled:
    def test_defaults_to_false(self) -> None:
        assert load_settings().database_pooled is False

    def test_reads_true(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_DATABASE_POOLED", "true")

        assert load_settings().database_pooled is True
