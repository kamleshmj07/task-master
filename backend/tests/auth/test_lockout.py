"""Tests for login throttling, driven by a fake clock, on both stores."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, func, select

from task_master.auth import lockout
from task_master.auth.lockout import (
    LockoutPolicy,
    LoginThrottle,
    MemoryThrottleStore,
    PostgresThrottleStore,
    ThrottleStore,
    account_key,
    ip_key,
)
from task_master.database import create_engine, create_session_factory
from task_master.models import LoginAccountFailure, LoginIpFailure

pytestmark = pytest.mark.anyio

IP = "203.0.113.7"
EMAIL = "ada@example.com"
POLICY = LockoutPolicy(
    free_failures=5,
    base_lock_seconds=60,
    max_lock_seconds=900,
    ip_failures=20,
    ip_window_seconds=900,
)


class FakeClock:
    """Unix clock that only moves when told to."""

    def __init__(self) -> None:
        self.now = 1_800_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(params=["memory", pytest.param("postgres", marks=pytest.mark.db)])
async def store(request: pytest.FixtureRequest) -> AsyncIterator[ThrottleStore]:
    """Each throttle test runs on the in-memory store and on Postgres."""
    if request.param == "memory":
        yield MemoryThrottleStore()
        return
    migrated_db: str = request.getfixturevalue("migrated_db")
    engine = create_engine(migrated_db)
    session_factory = create_session_factory(engine)
    try:
        yield PostgresThrottleStore(session_factory)
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(delete(LoginAccountFailure))
            await session.execute(delete(LoginIpFailure))
        await engine.dispose()


@pytest.fixture
def throttle(store: ThrottleStore, clock: FakeClock) -> LoginThrottle:
    return LoginThrottle(POLICY, store, clock=clock)


async def fail(
    throttle: LoginThrottle, times: int, email: str = EMAIL, ip: str = IP
) -> None:
    for _ in range(times):
        await throttle.record_failure(ip, email)


class TestAccountBackoff:
    async def test_allows_a_fresh_account(self, throttle: LoginThrottle) -> None:
        assert await throttle.retry_after(IP, EMAIL) == 0

    async def test_first_failures_are_free(self, throttle: LoginThrottle) -> None:
        await fail(throttle, 4)

        assert await throttle.retry_after(IP, EMAIL) == 0

    async def test_fifth_failure_locks_for_base_time(
        self, throttle: LoginThrottle
    ) -> None:
        await fail(throttle, 5)

        assert await throttle.retry_after(IP, EMAIL) == 60

    @pytest.mark.parametrize(
        ("failures", "lock"), [(6, 120), (7, 240), (8, 480), (9, 900), (12, 900)]
    )
    async def test_each_further_failure_doubles_up_to_max(
        self, throttle: LoginThrottle, failures: int, lock: int
    ) -> None:
        await fail(throttle, failures)

        assert await throttle.retry_after(IP, EMAIL) == lock

    async def test_lock_expires(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        await fail(throttle, 5)

        clock.advance(60)

        assert await throttle.retry_after(IP, EMAIL) == 0

    async def test_failure_after_lock_doubles_it(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        await fail(throttle, 5)
        clock.advance(60)

        await fail(throttle, 1)

        assert await throttle.retry_after(IP, EMAIL) == 120

    async def test_success_clears_the_record(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        await fail(throttle, 5)
        clock.advance(60)
        await throttle.record_success(EMAIL)

        await fail(throttle, 4)

        assert await throttle.retry_after(IP, EMAIL) == 0

    async def test_record_is_forgotten_after_a_quiet_period(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        await fail(throttle, 4)
        clock.advance(900)

        await fail(throttle, 1)

        assert await throttle.retry_after(IP, EMAIL) == 0

    async def test_treats_email_case_and_spaces_as_one_account(
        self, throttle: LoginThrottle
    ) -> None:
        await fail(throttle, 5, email=" ADA@Example.com ")

        assert await throttle.retry_after(IP, EMAIL) == 60

    async def test_locks_accounts_independently(self, throttle: LoginThrottle) -> None:
        await fail(throttle, 5)

        assert await throttle.retry_after(IP, "grace@example.com") == 0

    async def test_locked_account_is_locked_from_every_ip(
        self, throttle: LoginThrottle
    ) -> None:
        await fail(throttle, 5)

        assert await throttle.retry_after("198.51.100.1", EMAIL) == 60


class TestIpBudget:
    async def test_blocks_ip_spraying_many_accounts(
        self, throttle: LoginThrottle
    ) -> None:
        for index in range(20):
            await fail(throttle, 1, email=f"user{index}@example.com")

        assert await throttle.retry_after(IP, "new@example.com") == 900

    async def test_other_ips_are_unaffected(self, throttle: LoginThrottle) -> None:
        for index in range(20):
            await fail(throttle, 1, email=f"user{index}@example.com")

        assert await throttle.retry_after("198.51.100.1", "new@example.com") == 0

    async def test_budget_frees_up_as_failures_age(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        for index in range(20):
            await fail(throttle, 1, email=f"user{index}@example.com")
            clock.advance(10)

        clock.advance(900 - 200)

        assert await throttle.retry_after(IP, "new@example.com") == 0


class TestKeys:
    def test_account_key_does_not_contain_the_email(self) -> None:
        assert "ada" not in account_key(EMAIL)

    def test_account_key_normalises_case_and_whitespace(self) -> None:
        assert account_key(" Ada@Example.COM ") == account_key(EMAIL)

    def test_ip_key_does_not_contain_the_address(self) -> None:
        assert "203.0" not in ip_key(IP)


class TestSharedStore:
    """Two API processes, each with its own throttle, sharing Postgres."""

    @pytest.mark.db
    async def test_failures_from_every_process_add_up(
        self, migrated_db: str, clock: FakeClock
    ) -> None:
        engine = create_engine(migrated_db)
        session_factory = create_session_factory(engine)
        first = LoginThrottle(POLICY, PostgresThrottleStore(session_factory), clock)
        second = LoginThrottle(POLICY, PostgresThrottleStore(session_factory), clock)
        try:
            await fail(first, 3)
            await fail(second, 2)

            assert await first.retry_after(IP, EMAIL) == 60
        finally:
            async with session_factory() as session, session.begin():
                await session.execute(delete(LoginAccountFailure))
                await session.execute(delete(LoginIpFailure))
            await engine.dispose()

    @pytest.mark.db
    async def test_stores_only_hashes(self, migrated_db: str, clock: FakeClock) -> None:
        engine = create_engine(migrated_db)
        session_factory = create_session_factory(engine)
        throttle = LoginThrottle(POLICY, PostgresThrottleStore(session_factory), clock)
        try:
            await fail(throttle, 1)

            async with session_factory() as session:
                account = await session.scalar(select(LoginAccountFailure.account_key))
                ip = await session.scalar(select(LoginIpFailure.ip_key))
            assert (account, ip) == (account_key(EMAIL), ip_key(IP))
        finally:
            async with session_factory() as session, session.begin():
                await session.execute(delete(LoginAccountFailure))
                await session.execute(delete(LoginIpFailure))
            await engine.dispose()

    @pytest.mark.db
    async def test_failures_prune_what_no_longer_counts(
        self, migrated_db: str, clock: FakeClock
    ) -> None:
        engine = create_engine(migrated_db)
        session_factory = create_session_factory(engine)
        throttle = LoginThrottle(POLICY, PostgresThrottleStore(session_factory), clock)
        try:
            await fail(throttle, 1, email="old@example.com", ip="10.0.0.1")
            clock.advance(900)

            await fail(throttle, 1, email="new@example.com", ip="10.0.0.2")

            async with session_factory() as session:
                accounts = await session.scalar(
                    select(func.count(LoginAccountFailure.account_key))
                )
                ips = await session.scalar(select(func.count(LoginIpFailure.id)))
            assert (accounts, ips) == (1, 1)
        finally:
            async with session_factory() as session, session.begin():
                await session.execute(delete(LoginAccountFailure))
                await session.execute(delete(LoginIpFailure))
            await engine.dispose()


class TestMemoryPruning:
    async def test_drops_stale_records_past_threshold(
        self, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(lockout, "PRUNE_THRESHOLD", 2)
        store = MemoryThrottleStore()
        throttle = LoginThrottle(POLICY, store, clock=clock)
        await fail(throttle, 1, email="old1@example.com", ip="10.0.0.1")
        await fail(throttle, 1, email="old2@example.com", ip="10.0.0.2")
        clock.advance(900)

        await fail(throttle, 1, email="new@example.com", ip="10.0.0.3")

        accounts = store._accounts  # pyright: ignore[reportPrivateUsage]
        ips = store._ip_failures  # pyright: ignore[reportPrivateUsage]
        assert (len(accounts), len(ips)) == (1, 1)
