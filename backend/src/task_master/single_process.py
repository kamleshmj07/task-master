"""Make sure production runs exactly one API process.

Rate limits and login throttling keep their counters in process memory. With
two processes each would count separately and the limits would silently
double, so in production the API holds a Postgres advisory lock for its whole
life and a second process refuses to start.

Known shortcoming: this caps the API at one process. Moving the counters to
Redis (or another shared store) lifts it; see CLAUDE.md.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

# Any fixed number; it only has to be the same for every API process.
LOCK_KEY = 7_340_915_201


class SecondProcessError(RuntimeError):
    """Raised when another API process already holds the lock."""


async def hold_single_process_lock(engine: AsyncEngine) -> AsyncConnection:
    """Take the lock and return the connection holding it; close it to release.

    Raises `SecondProcessError` when another process holds it.
    """
    connection = await engine.connect()
    locked = await connection.scalar(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}
    )
    if not locked:
        await connection.close()
        raise SecondProcessError(
            "Another Task Master API process is already running. Production runs "
            "a single process because rate limits are kept in memory."
        )
    return connection
