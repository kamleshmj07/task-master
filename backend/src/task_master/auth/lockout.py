"""Login throttling: per-account backoff plus a per-IP failure budget.

Only failed logins count. An account may fail a few times freely; after that
each failure locks it for twice as long as the last (capped), and a successful
login clears its record. Separately, each IP may fail a fixed number of times
per window across all accounts, which catches one client trying many emails.

Accounts are keyed by a hash of the normalised email, whether or not the
account exists, so the throttle never reveals which emails are registered;
client addresses are hashed too. Locks are temporary by design: a permanent
lock would let anyone lock a real user out.

Development and tests keep this state in memory. Production keeps it in
Postgres, so every API process sees the same failures and locks.
"""

import hashlib
import logging
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_master.models import LoginAccountFailure, LoginIpFailure

logger = logging.getLogger(__name__)

# The in-memory store prunes once this many accounts or IPs are tracked.
PRUNE_THRESHOLD = 10_000


@dataclass(frozen=True)
class LockoutPolicy:
    """Tunable limits for `LoginThrottle`."""

    free_failures: int = 5
    base_lock_seconds: float = 60
    max_lock_seconds: float = 900
    ip_failures: int = 20
    ip_window_seconds: float = 900


@dataclass(frozen=True)
class AccountRecord:
    """An account's recent failures; times are Unix seconds."""

    failures: int
    last_failure: float
    locked_until: float


def account_key(email: str) -> str:
    """Hash of the normalised email, so raw emails are never stored or logged."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def ip_key(ip: str) -> str:
    """Hash of a client address, so raw addresses are never stored."""
    return hashlib.sha256(ip.encode()).hexdigest()


class ThrottleStore(Protocol):
    """Where failed logins are kept."""

    async def account(self, key: str) -> AccountRecord | None:
        """The account's record, if any."""
        ...

    async def update_account(
        self, key: str, change: Callable[[AccountRecord | None], AccountRecord]
    ) -> AccountRecord:
        """Replace the account's record with `change(old)`, atomically."""
        ...

    async def forget_account(self, key: str) -> None:
        """Remove the account's record."""
        ...

    async def add_ip_failure(self, key: str, at: float) -> None:
        """Remember one failure from the address."""
        ...

    async def ip_failures(self, key: str, since: float) -> tuple[int, float | None]:
        """How many failures the address had after `since`, and the earliest."""
        ...

    async def prune(self, account_cutoff: float, ip_cutoff: float) -> None:
        """Drop records quiet since `account_cutoff` and failures before `ip_cutoff`."""
        ...


class LoginThrottle:
    """Decide whether a login may be attempted, and learn from its outcome."""

    def __init__(
        self,
        policy: LockoutPolicy,
        store: ThrottleStore,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._policy = policy
        self._store = store
        self._clock = clock

    async def retry_after(self, ip: str, email: str) -> int:
        """Seconds until a login may be attempted; 0 means go ahead."""
        now = self._clock()
        record = await self._store.account(account_key(email))
        account_wait = max(record.locked_until - now, 0) if record else 0
        return math.ceil(max(account_wait, await self._ip_wait(ip_key(ip), now)))

    async def record_failure(self, ip: str, email: str) -> None:
        """Count a failed login against both the account and the IP."""
        now = self._clock()
        key = account_key(email)

        def change(record: AccountRecord | None) -> AccountRecord:
            fresh = record if record and self._is_fresh(record, now) else None
            failures = (fresh.failures if fresh else 0) + 1
            return AccountRecord(failures, now, now + self._lock_seconds(failures))

        record = await self._store.update_account(key, change)
        if record.locked_until > now:
            logger.warning("Login locked for account %s", key[:12])
        await self._store.add_ip_failure(ip_key(ip), now)
        policy = self._policy
        await self._store.prune(
            now - policy.max_lock_seconds, now - policy.ip_window_seconds
        )

    async def record_success(self, email: str) -> None:
        """Forget an account's failures after it logs in."""
        await self._store.forget_account(account_key(email))

    def _lock_seconds(self, failures: int) -> float:
        """0 while failures are free, then base, 2x base, 4x base... up to max."""
        policy = self._policy
        if failures < policy.free_failures:
            return 0
        doublings = failures - policy.free_failures
        return min(policy.base_lock_seconds * 2**doublings, policy.max_lock_seconds)

    def _is_fresh(self, record: AccountRecord, now: float) -> bool:
        """False once the account went quiet long enough to be forgotten."""
        quiet_for = now - max(record.last_failure, record.locked_until)
        return quiet_for < self._policy.max_lock_seconds

    async def _ip_wait(self, key: str, now: float) -> float:
        window = self._policy.ip_window_seconds
        count, earliest = await self._store.ip_failures(key, now - window)
        if earliest is None or count < self._policy.ip_failures:
            return 0
        return earliest + window - now


class MemoryThrottleStore:
    """Failed logins in this process only; for development and tests."""

    def __init__(self) -> None:
        self._accounts: dict[str, AccountRecord] = {}
        self._ip_failures: dict[str, deque[float]] = {}

    async def account(self, key: str) -> AccountRecord | None:
        """The account's record, if any."""
        return self._accounts.get(key)

    async def update_account(
        self, key: str, change: Callable[[AccountRecord | None], AccountRecord]
    ) -> AccountRecord:
        """Replace the account's record with `change(old)`."""
        record = change(self._accounts.get(key))
        self._accounts[key] = record
        return record

    async def forget_account(self, key: str) -> None:
        """Remove the account's record."""
        self._accounts.pop(key, None)

    async def add_ip_failure(self, key: str, at: float) -> None:
        """Remember one failure from the address."""
        self._ip_failures.setdefault(key, deque()).append(at)

    async def ip_failures(self, key: str, since: float) -> tuple[int, float | None]:
        """How many failures the address had after `since`, and the earliest."""
        recent = [at for at in self._ip_failures.get(key, ()) if at > since]
        return len(recent), recent[0] if recent else None

    async def prune(self, account_cutoff: float, ip_cutoff: float) -> None:
        """Bound memory by dropping what no longer affects anything."""
        if len(self._accounts) > PRUNE_THRESHOLD:
            self._accounts = {
                key: record
                for key, record in self._accounts.items()
                if max(record.last_failure, record.locked_until) > account_cutoff
            }
        if len(self._ip_failures) > PRUNE_THRESHOLD:
            kept = {
                key: deque(at for at in failures if at > ip_cutoff)
                for key, failures in self._ip_failures.items()
            }
            self._ip_failures = {
                key: failures for key, failures in kept.items() if failures
            }


class PostgresThrottleStore:
    """Failed logins shared by every API process."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def account(self, key: str) -> AccountRecord | None:
        """The account's record, if any."""
        async with self._session_factory() as session:
            row = await session.get(LoginAccountFailure, key)
            return _record(row) if row else None

    async def update_account(
        self, key: str, change: Callable[[AccountRecord | None], AccountRecord]
    ) -> AccountRecord:
        """Lock the account's row, apply `change`, and save it in one transaction."""
        async with self._session_factory() as session, session.begin():
            # Make sure a row exists to lock; failures=0 marks "no record yet".
            await session.execute(
                insert(LoginAccountFailure)
                .values(
                    account_key=key,
                    failures=0,
                    last_failure=_moment(0),
                    locked_until=_moment(0),
                )
                .on_conflict_do_nothing()
            )
            row = await session.get(LoginAccountFailure, key, with_for_update=True)
            if row is None:  # pragma: no cover - inserted just above
                raise RuntimeError("Login failure row vanished")
            record = change(_record(row) if row.failures else None)
            row.failures = record.failures
            row.last_failure = _moment(record.last_failure)
            row.locked_until = _moment(record.locked_until)
            return record

    async def forget_account(self, key: str) -> None:
        """Remove the account's record."""
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(LoginAccountFailure).where(
                    LoginAccountFailure.account_key == key
                )
            )

    async def add_ip_failure(self, key: str, at: float) -> None:
        """Remember one failure from the address."""
        async with self._session_factory() as session, session.begin():
            session.add(LoginIpFailure(ip_key=key, failed_at=_moment(at)))

    async def ip_failures(self, key: str, since: float) -> tuple[int, float | None]:
        """How many failures the address had after `since`, and the earliest."""
        async with self._session_factory() as session:
            count, earliest = (
                await session.execute(
                    select(func.count(), func.min(LoginIpFailure.failed_at)).where(
                        LoginIpFailure.ip_key == key,
                        LoginIpFailure.failed_at > _moment(since),
                    )
                )
            ).one()
        return count, earliest.timestamp() if earliest else None

    async def prune(self, account_cutoff: float, ip_cutoff: float) -> None:
        """Delete quiet accounts and IP failures older than the cutoffs."""
        cutoff = _moment(account_cutoff)
        async with self._session_factory() as session, session.begin():
            await session.execute(
                delete(LoginAccountFailure).where(
                    LoginAccountFailure.last_failure <= cutoff,
                    LoginAccountFailure.locked_until <= cutoff,
                )
            )
            await session.execute(
                delete(LoginIpFailure).where(
                    LoginIpFailure.failed_at <= _moment(ip_cutoff)
                )
            )


def _moment(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)


def _record(row: LoginAccountFailure) -> AccountRecord:
    return AccountRecord(
        row.failures, row.last_failure.timestamp(), row.locked_until.timestamp()
    )
