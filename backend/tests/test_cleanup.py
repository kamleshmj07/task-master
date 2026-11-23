"""Tests for the finished-task clean-up job."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master import cleanup
from task_master.cleanup import purge_completed_tasks, purge_read_notifications
from task_master.models import Goal, Notification, NotificationKind, Task, TaskStatus
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


async def remaining_ids(session: AsyncSession) -> set[object]:
    return set(await session.scalars(select(Task.id)))


@pytest.mark.anyio
@pytest.mark.db
class TestPurgeCompletedTasks:
    async def test_deletes_tasks_finished_before_the_cutoff(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        await finished_task(db_session, goal, CUTOFF - timedelta(days=1))

        deleted = await purge_completed_tasks(db_session, CUTOFF)

        assert (deleted, await remaining_ids(db_session)) == (1, set())

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
