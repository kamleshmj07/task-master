"""Clean-up job: delete tasks finished longer ago than the retention period.

Finished tasks stay visible under Done for `completed_task_retention_days`
(default 90) and are then deleted (those of active goals are kept until the
goal is completed or archived) with their steps, postponements and plan
slots. Read notifications older than that go too. Run it on a schedule, e.g. daily:

    uv run python -m task_master.cleanup
"""

import sys
from datetime import datetime, timedelta

import anyio
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.config import get_settings
from task_master.database import create_engine, create_session_factory
from task_master.models import (
    Goal,
    GoalStatus,
    Notification,
    Task,
    TaskStatus,
    utc_now,
)


async def purge_completed_tasks(session: AsyncSession, cutoff: datetime) -> int:
    """Delete tasks completed before `cutoff`; return how many went.

    A finished task of an active goal is kept, so the goal's progress stays
    whole. Once the goal is completed or archived, its finished tasks go
    after the same retention period, counted from when the goal last changed.
    """
    settled_goals = select(Goal.id).where(
        Goal.status != GoalStatus.ACTIVE, Goal.updated_at < cutoff
    )
    result = await session.execute(
        delete(Task)
        .where(
            Task.status == TaskStatus.DONE,
            Task.completed_at < cutoff,
            or_(Task.goal_id.is_(None), Task.goal_id.in_(settled_goals)),
        )
        .returning(Task.id)
    )
    deleted = len(result.all())
    await session.commit()
    return deleted


async def purge_read_notifications(session: AsyncSession, cutoff: datetime) -> int:
    """Delete read notifications created before `cutoff`; return how many went."""
    result = await session.execute(
        delete(Notification)
        .where(Notification.read_at.is_not(None), Notification.created_at < cutoff)
        .returning(Notification.id)
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
            await purge_read_notifications(session, cutoff)
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
