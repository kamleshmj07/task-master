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
