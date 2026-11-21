"""Tests for login throttling, driven by a fake clock."""

import pytest

from task_master.auth import lockout
from task_master.auth.lockout import LockoutPolicy, LoginThrottle, account_key

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
    """Monotonic clock that only moves when told to."""

    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def throttle(clock: FakeClock) -> LoginThrottle:
    return LoginThrottle(POLICY, clock=clock)


def fail(throttle: LoginThrottle, times: int, email: str = EMAIL, ip: str = IP) -> None:
    for _ in range(times):
        throttle.record_failure(ip, email)


class TestAccountBackoff:
    def test_allows_a_fresh_account(self, throttle: LoginThrottle) -> None:
        assert throttle.retry_after(IP, EMAIL) == 0

    def test_first_failures_are_free(self, throttle: LoginThrottle) -> None:
        fail(throttle, 4)

        assert throttle.retry_after(IP, EMAIL) == 0

    def test_fifth_failure_locks_for_base_time(self, throttle: LoginThrottle) -> None:
        fail(throttle, 5)

        assert throttle.retry_after(IP, EMAIL) == 60

    @pytest.mark.parametrize(
        ("failures", "lock"), [(6, 120), (7, 240), (8, 480), (9, 900), (12, 900)]
    )
    def test_each_further_failure_doubles_up_to_max(
        self, throttle: LoginThrottle, failures: int, lock: int
    ) -> None:
        fail(throttle, failures)

        assert throttle.retry_after(IP, EMAIL) == lock

    def test_lock_expires(self, throttle: LoginThrottle, clock: FakeClock) -> None:
        fail(throttle, 5)

        clock.advance(60)

        assert throttle.retry_after(IP, EMAIL) == 0

    def test_failure_after_lock_doubles_it(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        fail(throttle, 5)
        clock.advance(60)

        fail(throttle, 1)

        assert throttle.retry_after(IP, EMAIL) == 120

    def test_success_clears_the_record(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        fail(throttle, 5)
        clock.advance(60)
        throttle.record_success(EMAIL)

        fail(throttle, 4)

        assert throttle.retry_after(IP, EMAIL) == 0

    def test_record_is_forgotten_after_a_quiet_period(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        fail(throttle, 4)
        clock.advance(900)

        fail(throttle, 1)

        assert throttle.retry_after(IP, EMAIL) == 0

    def test_treats_email_case_and_spaces_as_one_account(
        self, throttle: LoginThrottle
    ) -> None:
        fail(throttle, 5, email=" ADA@Example.com ")

        assert throttle.retry_after(IP, EMAIL) == 60

    def test_locks_accounts_independently(self, throttle: LoginThrottle) -> None:
        fail(throttle, 5)

        assert throttle.retry_after(IP, "grace@example.com") == 0

    def test_locked_account_is_locked_from_every_ip(
        self, throttle: LoginThrottle
    ) -> None:
        fail(throttle, 5)

        assert throttle.retry_after("198.51.100.1", EMAIL) == 60


class TestIpBudget:
    def test_blocks_ip_spraying_many_accounts(self, throttle: LoginThrottle) -> None:
        for index in range(20):
            fail(throttle, 1, email=f"user{index}@example.com")

        assert throttle.retry_after(IP, "new@example.com") == 900

    def test_other_ips_are_unaffected(self, throttle: LoginThrottle) -> None:
        for index in range(20):
            fail(throttle, 1, email=f"user{index}@example.com")

        assert throttle.retry_after("198.51.100.1", "new@example.com") == 0

    def test_budget_frees_up_as_failures_age(
        self, throttle: LoginThrottle, clock: FakeClock
    ) -> None:
        for index in range(20):
            fail(throttle, 1, email=f"user{index}@example.com")
            clock.advance(10)

        clock.advance(900 - 200)

        assert throttle.retry_after(IP, "new@example.com") == 0


class TestAccountKey:
    def test_does_not_contain_the_email(self) -> None:
        assert "ada" not in account_key(EMAIL)

    def test_normalises_case_and_whitespace(self) -> None:
        assert account_key(" Ada@Example.COM ") == account_key(EMAIL)


class TestPruning:
    def test_drops_stale_records_past_threshold(
        self,
        throttle: LoginThrottle,
        clock: FakeClock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(lockout, "PRUNE_THRESHOLD", 2)
        fail(throttle, 1, email="old1@example.com", ip="10.0.0.1")
        fail(throttle, 1, email="old2@example.com", ip="10.0.0.2")
        clock.advance(900)

        fail(throttle, 1, email="new@example.com", ip="10.0.0.3")

        accounts = throttle._accounts  # pyright: ignore[reportPrivateUsage]
        ips = throttle._ip_failures  # pyright: ignore[reportPrivateUsage]
        assert (len(accounts), len(ips)) == (1, 1)
