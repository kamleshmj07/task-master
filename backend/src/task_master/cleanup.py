"""Clean-up job: delete tasks finished longer ago than the retention period.

Finished tasks stay visible under Done for `completed_task_retention_days`
(default 90) and are then deleted with their steps, postponements and plan
slots. Run it on a schedule, e.g. daily:

    uv run python -m task_master.cleanup
"""

import sys
from datetime import datetime, timedelta

import anyio
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.config import get_settings
from task_master.database import create_engine, create_session_factory
from task_master.models import Task, TaskStatus, utc_now


async def purge_completed_tasks(session: AsyncSession, cutoff: datetime) -> int:
    """Delete every task completed before `cutoff`; return how many went."""
    result = await session.execute(
        delete(Task)
        .where(Task.status == TaskStatus.DONE, Task.completed_at < cutoff)
        .returning(Task.id)
    )
    deleted = len(result.all())
    await session.commit()
    return deleted


async def run(now: datetime) -> int:
    """Purge with the configured retention period against the app database."""
    settings = get_settings()
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        async with create_session_factory(engine)() as session:
            cutoff = now - timedelta(days=settings.completed_task_retention_days)
            return await purge_completed_tasks(session, cutoff)
    finally:
        await engine.dispose()


def main() -> int:
    """Command-line entry point; prints how many tasks were deleted."""
    deleted = anyio.run(run, utc_now())
    print(f"Deleted {deleted} finished task(s) past the retention period.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
