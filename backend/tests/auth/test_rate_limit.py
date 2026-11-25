"""Tests for the fixed-window rate limiter, in memory and in Postgres."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, func, select

from task_master.auth import rate_limit
from task_master.auth.rate_limit import (
    MemoryWindowStore,
    PostgresWindowStore,
    RateLimiter,
    hash_key,
    purge_expired_windows,
)
from task_master.database import create_engine, create_session_factory
from task_master.models import RateLimitWindow

pytestmark = pytest.mark.anyio

START = 1_800_000_000.0  # a whole minute, so windows start here


class FakeClock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def shared_store(migrated_db: str) -> AsyncIterator[PostgresWindowStore]:
    """A Postgres store, emptied afterwards."""
    engine = create_engine(migrated_db)
    session_factory = create_session_factory(engine)
    try:
        yield PostgresWindowStore(session_factory)
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(delete(RateLimitWindow))
        await engine.dispose()


class TestRateLimiter:
    async def test_allows_requests_up_to_the_limit(self) -> None:
        limiter = RateLimiter("2/minute", MemoryWindowStore())

        assert [await limiter.hit("client"), await limiter.hit("client")] == [
            True,
            True,
        ]

    async def test_blocks_requests_over_the_limit(self) -> None:
        limiter = RateLimiter("1/minute", MemoryWindowStore())
        await limiter.hit("client")

        assert await limiter.hit("client") is False

    async def test_counts_keys_separately(self) -> None:
        limiter = RateLimiter("1/minute", MemoryWindowStore())
        await limiter.hit("one")

        assert await limiter.hit("two") is True

    async def test_refills_in_the_next_window(self, clock: FakeClock) -> None:
        limiter = RateLimiter("1/minute", MemoryWindowStore(), clock)
        await limiter.hit("client")

        clock.now = START + 60

        assert await limiter.hit("client") is True

    def test_reports_window_length(self) -> None:
        assert RateLimiter("5/hour", MemoryWindowStore()).window_seconds == 3600

    def test_hash_key_hides_the_value(self) -> None:
        assert "203.0" not in hash_key("203.0.113.7")


class TestMemoryWindowStore:
    async def test_forgets_ended_windows_past_threshold(
        self, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(rate_limit, "PRUNE_THRESHOLD", 1)
        store = MemoryWindowStore()
        limiter = RateLimiter("5/minute", store, clock)
        await limiter.hit("one")
        await limiter.hit("two")
        clock.now = START + 60

        await limiter.hit("three")

        assert len(store._hits) == 1  # pyright: ignore[reportPrivateUsage]


@pytest.mark.db
class TestPostgresWindowStore:
    async def test_limits_like_memory(
        self, shared_store: PostgresWindowStore, clock: FakeClock
    ) -> None:
        limiter = RateLimiter("2/minute", shared_store, clock)

        results = [await limiter.hit("client") for _ in range(3)]

        assert results == [True, True, False]

    async def test_processes_share_one_budget(
        self, shared_store: PostgresWindowStore, clock: FakeClock
    ) -> None:
        first = RateLimiter("2/minute", shared_store, clock)
        second = RateLimiter("2/minute", shared_store, clock)
        await first.hit("client")
        await second.hit("client")

        assert await first.hit("client") is False

    async def test_refills_in_the_next_window(
        self, shared_store: PostgresWindowStore, clock: FakeClock
    ) -> None:
        limiter = RateLimiter("1/minute", shared_store, clock)
        await limiter.hit("client")

        clock.now = START + 60

        assert await limiter.hit("client") is True

    async def test_cleanup_deletes_only_ended_windows(
        self, shared_store: PostgresWindowStore, clock: FakeClock, migrated_db: str
    ) -> None:
        limiter = RateLimiter("5/minute", shared_store, clock)
        await limiter.hit("old")
        clock.now = START + 60
        await limiter.hit("current")
        engine = create_engine(migrated_db)
        try:
            async with create_session_factory(engine)() as session:
                deleted = await purge_expired_windows(
                    session, datetime.fromtimestamp(START + 90, UTC)
                )
                left = await session.scalar(select(func.count(RateLimitWindow.key)))
        finally:
            await engine.dispose()

        assert (deleted, left) == (1, 1)
