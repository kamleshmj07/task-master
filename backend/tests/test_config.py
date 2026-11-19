"""Tests for settings loading."""

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from task_master.config import Settings


class EnvOnlySettings(Settings):
    """Settings that ignore any local `.env` file, so tests see only env vars."""

    model_config = SettingsConfigDict(env_file=None)


class TestSettings:
    def test_defaults_to_development(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TASK_MASTER_ENVIRONMENT", raising=False)

        assert EnvOnlySettings().environment == "development"

    def test_reads_prefixed_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_ENVIRONMENT", "production")

        assert EnvOnlySettings().environment == "production"

    def test_parses_cors_origins_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_CORS_ORIGINS", '["https://a.com"]')

        assert EnvOnlySettings().cors_origins == ["https://a.com"]

    def test_rejects_unknown_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TASK_MASTER_ENVIRONMENT", "staging")

        with pytest.raises(ValidationError):
            EnvOnlySettings()
