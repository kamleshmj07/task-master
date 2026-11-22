"""Login throttling: per-account backoff plus a per-IP failure budget.

Only failed logins count. An account may fail a few times freely; after that
each failure locks it for twice as long as the last (capped), and a successful
login clears its record. Separately, each IP may fail a fixed number of times
per window across all accounts, which catches one client trying many emails.

Accounts are keyed by a hash of the normalised email, whether or not the
account exists, so the throttle never reveals which emails are registered.
Locks are temporary by design: a permanent lock would let anyone lock a real
user out.

State lives in process memory: each worker throttles separately and state
resets on restart. Move to Redis before running several workers.
"""

import hashlib
import logging
import math
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Entries are pruned once this many accounts or IPs are tracked.
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
class _AccountRecord:
    failures: int
    last_failure: float
    locked_until: float


def account_key(email: str) -> str:
    """Hash of the normalised email, so raw emails never sit in memory or logs."""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


class LoginThrottle:
    """Decide whether a login may be attempted, and learn from its outcome."""

    def __init__(
        self,
        policy: LockoutPolicy,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._policy = policy
        self._clock = clock
        self._accounts: dict[str, _AccountRecord] = {}
        self._ip_failures: dict[str, deque[float]] = {}

    def retry_after(self, ip: str, email: str) -> int:
        """Seconds until a login may be attempted; 0 means go ahead."""
        now = self._clock()
        account_wait = self._account_wait(account_key(email), now)
        return math.ceil(max(account_wait, self._ip_wait(ip, now)))

    def record_failure(self, ip: str, email: str) -> None:
        """Count a failed login against both the account and the IP."""
        now = self._clock()
        key = account_key(email)
        record = self._fresh_record(key, now)
        failures = (record.failures if record else 0) + 1
        locked_until = now + self._lock_seconds(failures)
        self._accounts[key] = _AccountRecord(failures, now, locked_until)
        if locked_until > now:
            logger.warning("Login locked for account %s", key[:12])
        self._ip_failures.setdefault(ip, deque()).append(now)
        self._prune(now)

    def record_success(self, email: str) -> None:
        """Forget an account's failures after it logs in."""
        self._accounts.pop(account_key(email), None)

    def _lock_seconds(self, failures: int) -> float:
        """0 while failures are free, then base, 2x base, 4x base... up to max."""
        policy = self._policy
        if failures < policy.free_failures:
            return 0
        doublings = failures - policy.free_failures
        return min(policy.base_lock_seconds * 2**doublings, policy.max_lock_seconds)

    def _fresh_record(self, key: str, now: float) -> _AccountRecord | None:
        """The account's record, unless it went quiet long enough to forget."""
        record = self._accounts.get(key)
        if record is None:
            return None
        quiet_for = now - max(record.last_failure, record.locked_until)
        if quiet_for >= self._policy.max_lock_seconds:
            return None
        return record

    def _account_wait(self, key: str, now: float) -> float:
        record = self._accounts.get(key)
        return max(record.locked_until - now, 0) if record else 0

    def _ip_wait(self, ip: str, now: float) -> float:
        failures = self._recent_ip_failures(ip, now)
        if len(failures) < self._policy.ip_failures:
            return 0
        return failures[0] + self._policy.ip_window_seconds - now

    def _recent_ip_failures(self, ip: str, now: float) -> deque[float]:
        """Drop the IP's failures that fell out of the window; return the rest."""
        failures = self._ip_failures.get(ip, deque())
        cutoff = now - self._policy.ip_window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        return failures

    def _prune(self, now: float) -> None:
        """Bound memory by dropping records that no longer affect anything."""
        if len(self._accounts) > PRUNE_THRESHOLD:
            self._accounts = {
                key: record
                for key, record in self._accounts.items()
                if self._fresh_record(key, now) is not None
            }
        if len(self._ip_failures) > PRUNE_THRESHOLD:
            self._ip_failures = {
                ip: failures
                for ip in list(self._ip_failures)
                if (failures := self._recent_ip_failures(ip, now))
            }
