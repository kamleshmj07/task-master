"""Shared test fixtures."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from task_master.config import Settings
from task_master.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio via anyio."""
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    """Settings for the test environment."""
    return Settings(environment="test", cors_origins=["http://test.local"])


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to a fresh app instance."""
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
