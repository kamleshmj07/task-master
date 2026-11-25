"""Tests for the health endpoint."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


class TestHealth:
    async def test_returns_200(self, client: AsyncClient) -> None:
        response = await client.get("/health")

        assert response.status_code == 200

    async def test_returns_ok_status(self, client: AsyncClient) -> None:
        response = await client.get("/health")

        assert response.json() == {"status": "ok"}

    async def test_rejects_post_with_405(self, client: AsyncClient) -> None:
        response = await client.post("/health")

        assert response.status_code == 405


class TestReadiness:
    @pytest.mark.db
    async def test_ok_when_the_database_answers(self, api_client: AsyncClient) -> None:
        response = await api_client.get("/health/ready")

        assert (response.status_code, response.json()) == (200, {"status": "ok"})

    async def test_503_when_the_database_is_unreachable(
        self, client: AsyncClient
    ) -> None:
        # The `client` fixture's database URL points nowhere.
        response = await client.get("/health/ready")

        assert (response.status_code, response.json()) == (
            503,
            {"status": "unavailable"},
        )
