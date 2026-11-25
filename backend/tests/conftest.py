"""Shared test fixtures."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import delete, make_url
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.config import Settings
from task_master.database import create_engine, create_session_factory
from task_master.dependencies import get_now, get_session
from task_master.main import create_app
from task_master.models import RateLimitWindow

ALEMBIC_INI = Path(__file__).parents[1] / "alembic.ini"
# API tests run at this moment, so "today" is always 2026-11-22 in UTC.
FIXED_NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


class DatabaseTestSettings(BaseSettings):
    """Test database location, from `TASK_MASTER_TEST_DATABASE_URL`."""

    model_config = SettingsConfigDict(
        env_prefix="TASK_MASTER_TEST_", env_file=".env", extra="ignore"
    )

    database_url: SecretStr


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio via anyio."""
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    """Settings for the test environment."""
    return Settings(
        environment="test",
        cors_origins=["http://test.local"],
        database_url=SecretStr("postgresql+asyncpg://unused@localhost/unused"),
        auth_secret=SecretStr("test-auth-secret"),
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to a fresh app instance."""
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """URL of the dedicated test database; refuses anything not named *_test."""
    settings = DatabaseTestSettings()  # pyright: ignore[reportCallIssue]
    url = settings.database_url.get_secret_value()
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        raise RuntimeError(f"Refusing to run tests against database {database!r}")
    return url


@pytest.fixture(scope="session")
def alembic_config(test_database_url: str) -> Config:
    """Alembic config pointed at the test database."""
    config = Config(ALEMBIC_INI)
    config.set_main_option("sqlalchemy.url", test_database_url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session")
def migrated_db(alembic_config: Config, test_database_url: str) -> str:
    """Rebuild the test schema from migrations once per session."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    return test_database_url


@pytest.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """Session inside a transaction that is rolled back after each test."""
    engine = create_engine(migrated_db)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def api_client(
    settings: Settings, db_session: AsyncSession
) -> AsyncIterator[AsyncClient]:
    """HTTPS client whose requests share the rolled-back test session."""

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = create_app(settings)
    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        yield client


async def login_headers(client: AsyncClient, email: str) -> dict[str, str]:
    """Register `email`, log in on mobile, and return bearer auth headers."""
    password = "correct-horse-battery"
    await client.post("/auth/register", json={"email": email, "password": password})
    response = await client.post(
        "/auth/mobile/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def auth_headers(api_client: AsyncClient) -> dict[str, str]:
    """Bearer headers for a freshly registered user."""
    return await login_headers(api_client, "owner@example.com")


@pytest.fixture
async def other_headers(api_client: AsyncClient) -> dict[str, str]:
    """Bearer headers for a second, unrelated user."""
    return await login_headers(api_client, "stranger@example.com")


async def clear_rate_limit_windows(database_url: str) -> None:
    """Forget the request counts a production-mode app wrote to the database."""
    engine = create_engine(database_url)
    try:
        async with create_session_factory(engine)() as session, session.begin():
            await session.execute(delete(RateLimitWindow))
    finally:
        await engine.dispose()
