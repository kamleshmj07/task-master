"""Tests for app construction: CORS and docs exposure."""

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from task_master.config import Settings
from task_master.main import create_app
from tests.conftest import clear_rate_limit_windows

pytestmark = pytest.mark.anyio


async def _get(settings: Settings, path: str, origin: str | None = None) -> int:
    headers = {"Origin": origin} if origin else {}
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(path, headers=headers)
    return response.status_code


class TestCors:
    async def test_allows_configured_origin(self, client: AsyncClient) -> None:
        response = await client.get("/health", headers={"Origin": "http://test.local"})

        assert response.headers["access-control-allow-origin"] == "http://test.local"

    async def test_omits_header_for_unknown_origin(self, client: AsyncClient) -> None:
        response = await client.get("/health", headers={"Origin": "http://evil.com"})

        assert "access-control-allow-origin" not in response.headers


class TestDocs:
    async def test_exposes_docs_outside_production(self, settings: Settings) -> None:
        assert await _get(settings, "/docs") == 200

    @pytest.mark.db
    async def test_hides_docs_in_production(
        self, settings: Settings, migrated_db: str
    ) -> None:
        # Production counts requests in Postgres, so it needs a real database.
        settings = settings.model_copy(
            update={"environment": "production", "database_url": SecretStr(migrated_db)}
        )
        try:
            status = await _get(settings, "/docs")
        finally:
            await clear_rate_limit_windows(migrated_db)

        assert status == 404
