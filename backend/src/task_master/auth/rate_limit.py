"""Fixed-window rate limiting, with counters in memory or in Postgres.

Each key may make `amount` requests per window (for example 5 a minute);
windows are aligned to the clock, so a client's budget refills at the start
of each one. Development and tests count in memory. Production counts in
Postgres, so every API process shares one budget per client and the API can
run as many processes as it likes.
"""

import hashlib
import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import HTTPException, Request, status
from limits import parse
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from task_master.models import RateLimitWindow

logger = logging.getLogger(__name__)

Clock = Callable[[], float]

# The in-memory store forgets ended windows once it holds this many.
PRUNE_THRESHOLD = 10_000


def hash_key(value: str) -> str:
    """A short hash, so client addresses and tokens are never stored as is."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


class WindowStore(Protocol):
    """Where request counts per key and window are kept."""

    async def add_hit(self, key: str, window_start: int, window_seconds: int) -> int:
        """Count one request in the window; return the window's total so far."""
        ...


class MemoryWindowStore:
    """Counts in this process only; for development and tests.

    Give each limiter its own store: ended windows are dropped by start time.
    """

    def __init__(self) -> None:
        self._hits: dict[tuple[str, int], int] = {}

    async def add_hit(self, key: str, window_start: int, window_seconds: int) -> int:
        """Count one request; forget earlier windows once many are kept."""
        if len(self._hits) > PRUNE_THRESHOLD:
            self._hits = {
                slot: hits
                for slot, hits in self._hits.items()
                if slot[1] >= window_start
            }
        total = self._hits.get((key, window_start), 0) + 1
        self._hits[(key, window_start)] = total
        return total


class PostgresWindowStore:
    """Counts shared by every API process through one upsert per request."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add_hit(self, key: str, window_start: int, window_seconds: int) -> int:
        """Add one hit to the window's row, creating it if needed."""
        start = datetime.fromtimestamp(window_start, UTC)
        statement = (
            insert(RateLimitWindow)
            .values(
                key=key,
                window_start=start,
                hits=1,
                expires_at=start + timedelta(seconds=window_seconds),
            )
            .on_conflict_do_update(
                index_elements=[RateLimitWindow.key, RateLimitWindow.window_start],
                set_={"hits": RateLimitWindow.hits + 1},
            )
            .returning(RateLimitWindow.hits)
        )
        async with self._session_factory() as session, session.begin():
            return (await session.execute(statement)).scalar_one()


async def purge_expired_windows(session: AsyncSession, now: datetime) -> int:
    """Delete rate-limit windows that ended before `now`; return how many."""
    result = await session.execute(
        delete(RateLimitWindow)
        .where(RateLimitWindow.expires_at < now)
        .returning(RateLimitWindow.key)
    )
    deleted = len(result.all())
    await session.commit()
    return deleted


class RateLimiter:
    """Allows `limit` (e.g. "5/minute") requests per key and window."""

    def __init__(
        self, limit: str, store: WindowStore, clock: Clock = time.time
    ) -> None:
        item = parse(limit)
        self._amount = item.amount
        self._window = item.get_expiry()
        self._store = store
        self._clock = clock

    async def hit(self, key: str) -> bool:
        """Count one request for `key`; return False once over the limit."""
        window_start = math.floor(self._clock() / self._window) * self._window
        hits = await self._store.add_hit(key, window_start, self._window)
        return hits <= self._amount

    @property
    def window_seconds(self) -> int:
        """Length of the limit's window, sent as `Retry-After`."""
        return self._window


async def enforce_auth_rate_limit(request: Request) -> None:
    """Reject the request with 429 when its client exceeds the auth limit."""
    limiter: RateLimiter = request.app.state.auth_rate_limiter
    client = request.client.host if request.client else "unknown"
    if await limiter.hit(f"auth:{request.url.path}:{hash_key(client)}"):
        return
    logger.warning("Auth rate limit exceeded on %s", request.url.path)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests",
        headers={"Retry-After": str(limiter.window_seconds)},
    )
