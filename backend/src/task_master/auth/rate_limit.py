"""Per-client rate limiting for authentication endpoints.

Counters live in process memory, so each worker counts separately and counts
reset on restart. Move to Redis storage before running several workers.
"""

import logging

from fastapi import HTTPException, Request, status
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

logger = logging.getLogger(__name__)


class RateLimiter:
    """Moving-window limiter keyed by an arbitrary string."""

    def __init__(self, limit: str) -> None:
        self._item = parse(limit)
        self._limiter = MovingWindowRateLimiter(MemoryStorage())

    def hit(self, key: str) -> bool:
        """Count one request for `key`; return False once over the limit."""
        return self._limiter.hit(self._item, key)

    @property
    def window_seconds(self) -> int:
        """Length of the limit's window, sent as `Retry-After`."""
        return self._item.get_expiry()


async def enforce_auth_rate_limit(request: Request) -> None:
    """Reject the request with 429 when its client exceeds the auth limit."""
    limiter: RateLimiter = request.app.state.auth_rate_limiter
    client = request.client.host if request.client else "unknown"
    if limiter.hit(f"{request.url.path}:{client}"):
        return
    logger.warning("Auth rate limit exceeded on %s", request.url.path)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests",
        headers={"Retry-After": str(limiter.window_seconds)},
    )
