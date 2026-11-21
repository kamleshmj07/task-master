"""Smoke tests for the OpenAPI export command."""

import json
from pathlib import Path

import pytest

from task_master.openapi import main


class TestExport:
    def test_writes_schema_with_auth_routes(self, tmp_path: Path) -> None:
        output = tmp_path / "openapi.json"

        assert main([str(output)]) == 0
        assert "/auth/web/login" in json.loads(output.read_text())["paths"]

    def test_fails_without_output_path(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main([]) == 2
        assert "usage" in capsys.readouterr().err
