"""Tests for serving the API under a path prefix (e.g. "/api" on Vercel)."""

from collections.abc import AsyncIterator
from http.cookies import SimpleCookie

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.auth.routes import REFRESH_COOKIE
from task_master.config import Settings
from task_master.dependencies import get_now, get_session
from task_master.main import create_app
from tests.conftest import FIXED_NOW

pytestmark = pytest.mark.anyio

EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"


def prefixed(settings: Settings) -> Settings:
    return settings.model_copy(update={"api_prefix": "/api"})


async def get(settings: Settings, path: str) -> int:
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        return (await client.get(path)).status_code


@pytest.fixture
async def api_client_under_api(
    settings: Settings, db_session: AsyncSession
) -> AsyncIterator[AsyncClient]:
    """Like `api_client`, with every route under "/api"."""

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = create_app(prefixed(settings))
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client


class TestRoutes:
    async def test_serves_routes_under_the_prefix(self, settings: Settings) -> None:
        assert await get(prefixed(settings), "/api/health") == 200

    async def test_no_longer_serves_them_at_the_root(self, settings: Settings) -> None:
        assert await get(prefixed(settings), "/health") == 404

    async def test_serves_the_docs_under_the_prefix(self, settings: Settings) -> None:
        assert await get(prefixed(settings), "/api/docs") == 200

    async def test_health_stays_exempt_from_rate_limits(
        self, settings: Settings
    ) -> None:
        settings = prefixed(settings).model_copy(update={"api_rate_limit": "1/minute"})
        transport = ASGITransport(app=create_app(settings))
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            statuses = [(await client.get("/api/health")).status_code for _ in range(3)]

        assert statuses == [200, 200, 200]

    async def test_no_prefix_keeps_routes_at_the_root(self, settings: Settings) -> None:
        assert await get(settings, "/health") == 200


@pytest.mark.db
class TestRefreshCookie:
    async def test_cookie_path_includes_the_prefix(
        self, api_client_under_api: AsyncClient
    ) -> None:
        client = api_client_under_api
        await client.post(
            "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
        )

        response = await client.post(
            "/api/auth/web/login", data={"username": EMAIL, "password": PASSWORD}
        )

        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        assert cookie[REFRESH_COOKIE]["path"] == "/api/auth/web"

    async def test_refresh_works_under_the_prefix(
        self, api_client_under_api: AsyncClient
    ) -> None:
        client = api_client_under_api
        await client.post(
            "/api/auth/register", json={"email": EMAIL, "password": PASSWORD}
        )
        login = await client.post(
            "/api/auth/web/login", data={"username": EMAIL, "password": PASSWORD}
        )
        cookie = SimpleCookie()
        cookie.load(login.headers["set-cookie"])
        token = cookie[REFRESH_COOKIE].value

        response = await client.post(
            "/api/auth/web/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={token}"}
        )

        assert response.status_code == 200
