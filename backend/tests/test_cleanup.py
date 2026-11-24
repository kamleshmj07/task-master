"""Tests for the finished-task clean-up job."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from task_master import cleanup
from task_master.cleanup import purge_completed_tasks, purge_read_notifications
from task_master.models import (
    Goal,
    GoalStatus,
    Notification,
    NotificationKind,
    Task,
    TaskStatus,
)
from tests.factories import make_goal, make_task, make_user

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
CUTOFF = NOW - timedelta(days=90)


async def finished_task(
    session: AsyncSession, goal: Goal, completed_at: datetime
) -> Task:
    task = await make_task(session, goal)
    task.status = TaskStatus.DONE
    task.completed_at = completed_at
    await session.flush()
    return task


async def settle(
    session: AsyncSession, goal: Goal, status: GoalStatus, when: datetime
) -> None:
    """Complete or archive `goal`, as if it happened at `when`."""
    await session.execute(
        update(Goal).where(Goal.id == goal.id).values(status=status, updated_at=when)
    )


async def remaining_ids(session: AsyncSession) -> set[object]:
    return set(await session.scalars(select(Task.id)))


@pytest.mark.anyio
@pytest.mark.db
class TestPurgeCompletedTasks:
    async def test_deletes_goal_less_tasks_finished_before_the_cutoff(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        task = await finished_task(db_session, goal, CUTOFF - timedelta(days=1))
        task.goal_id = None
        await db_session.flush()

        deleted = await purge_completed_tasks(db_session, CUTOFF)

        assert (deleted, await remaining_ids(db_session)) == (1, set())

    async def test_keeps_finished_tasks_of_active_goals(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        task = await finished_task(db_session, goal, CUTOFF - timedelta(days=30))

        await purge_completed_tasks(db_session, CUTOFF)

        assert await remaining_ids(db_session) == {task.id}

    async def test_deletes_them_once_the_goal_settled_long_ago(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        await finished_task(db_session, goal, CUTOFF - timedelta(days=30))
        await settle(db_session, goal, GoalStatus.COMPLETED, CUTOFF - timedelta(days=1))

        assert await purge_completed_tasks(db_session, CUTOFF) == 1

    async def test_waits_after_the_goal_was_just_archived(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        task = await finished_task(db_session, goal, CUTOFF - timedelta(days=30))
        await settle(db_session, goal, GoalStatus.ARCHIVED, NOW)

        await purge_completed_tasks(db_session, CUTOFF)

        assert await remaining_ids(db_session) == {task.id}

    async def test_keeps_recently_finished_tasks(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        recent = await finished_task(db_session, goal, CUTOFF + timedelta(days=1))

        await purge_completed_tasks(db_session, CUTOFF)

        assert await remaining_ids(db_session) == {recent.id}

    async def test_never_deletes_open_tasks(self, db_session: AsyncSession) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        open_task = await make_task(db_session, goal)

        await purge_completed_tasks(db_session, NOW)

        assert await remaining_ids(db_session) == {open_task.id}


class TestMain:
    def test_reports_how_many_were_deleted(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        async def fake_run(now: datetime) -> int:
            return 3

        monkeypatch.setattr(cleanup, "run", fake_run)

        assert cleanup.main() == 0
        assert "Deleted 3 finished task(s)" in capsys.readouterr().out


@pytest.mark.anyio
@pytest.mark.db
class TestPurgeReadNotifications:
    async def notification(
        self, session: AsyncSession, created_at: datetime, read: bool
    ) -> Notification:
        user = await make_user(session)
        notification = Notification(
            user_id=user.id,
            kind=NotificationKind.TASKS_DUE_SOON,
            key=f"test:{created_at.isoformat()}:{read}",
            title="2 tasks are due in the next 3 days",
            body="Review them.",
            created_at=created_at,
            read_at=created_at if read else None,
        )
        session.add(notification)
        await session.flush()
        return notification

    async def test_deletes_old_read_notifications(
        self, db_session: AsyncSession
    ) -> None:
        await self.notification(db_session, CUTOFF - timedelta(days=1), read=True)

        assert await purge_read_notifications(db_session, CUTOFF) == 1

    async def test_keeps_unread_and_recent_ones(self, db_session: AsyncSession) -> None:
        await self.notification(db_session, CUTOFF - timedelta(days=1), read=False)
        await self.notification(db_session, CUTOFF + timedelta(days=1), read=True)

        assert await purge_read_notifications(db_session, CUTOFF) == 0
