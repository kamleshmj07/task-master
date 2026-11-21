"""Database tests for model defaults, constraints, and cascades."""

from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import (
    DailyPlanItem,
    Goal,
    GoalStatus,
    PostponeReason,
    Task,
    TaskPostponement,
    TaskStatus,
    User,
)
from tests.factories import make_goal, make_plan, make_task, make_user

pytestmark = [pytest.mark.anyio, pytest.mark.db]

TODAY = date(2026, 11, 19)


async def assert_rejected(session: AsyncSession, *rows: object) -> None:
    """Assert the database refuses to store `rows`."""
    session.add_all(rows)
    with pytest.raises(IntegrityError):
        await session.flush()


class TestUser:
    async def test_applies_defaults(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        assert (user.timezone, user.daily_capacity_minutes, user.is_active) == (
            "UTC",
            480,
            True,
        )

    async def test_rejects_duplicate_email(self, db_session: AsyncSession) -> None:
        await make_user(db_session, email="dup@example.com")

        await assert_rejected(
            db_session, User(email="dup@example.com", hashed_password="x")
        )

    async def test_rejects_zero_capacity(self, db_session: AsyncSession) -> None:
        user = User(email="a@example.com", hashed_password="x")
        user.daily_capacity_minutes = 0

        await assert_rejected(db_session, user)

    async def test_rejects_capacity_over_a_day(self, db_session: AsyncSession) -> None:
        user = User(email="a@example.com", hashed_password="x")
        user.daily_capacity_minutes = 1441

        await assert_rejected(db_session, user)


class TestGoal:
    async def test_defaults_to_active(self, db_session: AsyncSession) -> None:
        goal = await make_goal(db_session, await make_user(db_session))

        assert goal.status is GoalStatus.ACTIVE

    async def test_rejects_unknown_status(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)

        with pytest.raises(IntegrityError):
            await db_session.execute(
                text(
                    "INSERT INTO goal (id, user_id, title, status) "
                    "VALUES (gen_random_uuid(), :user_id, 'g', 'someday')"
                ),
                {"user_id": user.id},
            )

    async def test_deleting_user_removes_goals(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        await make_goal(db_session, user)

        await db_session.delete(user)
        await db_session.flush()

        assert (await db_session.scalars(select(Goal))).all() == []


class TestTask:
    async def test_applies_defaults(self, db_session: AsyncSession) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        task = await make_task(db_session, goal)

        assert (task.status, task.postpone_count) == (TaskStatus.TODO, 0)

    async def test_rejects_blank_next_action(self, db_session: AsyncSession) -> None:
        goal = await make_goal(db_session, await make_user(db_session))

        await assert_rejected(
            db_session,
            Task(user_id=goal.user_id, goal_id=goal.id, title="t", next_action="  "),
        )

    async def test_rejects_zero_estimate(self, db_session: AsyncSession) -> None:
        goal = await make_goal(db_session, await make_user(db_session))

        await assert_rejected(
            db_session,
            Task(
                user_id=goal.user_id,
                goal_id=goal.id,
                title="t",
                next_action="do it",
                estimate_minutes=0,
            ),
        )

    async def test_rejects_goal_owned_by_another_user(
        self, db_session: AsyncSession
    ) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        intruder = await make_user(db_session)

        await assert_rejected(
            db_session,
            Task(user_id=intruder.id, goal_id=goal.id, title="t", next_action="x"),
        )

    async def test_deleting_goal_removes_tasks(self, db_session: AsyncSession) -> None:
        goal = await make_goal(db_session, await make_user(db_session))
        await make_task(db_session, goal)

        await db_session.delete(goal)
        await db_session.flush()

        assert (await db_session.scalars(select(Task))).all() == []


def _postponement(
    task: Task, reason: PostponeReason, note: str | None = None
) -> TaskPostponement:
    return TaskPostponement(
        task_id=task.id,
        from_date=TODAY,
        to_date=date(2026, 11, 20),
        reason=reason,
        note=note,
    )


class TestTaskPostponement:
    async def test_stores_reason(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )
        postponement = TaskPostponement(
            task_id=task.id,
            from_date=TODAY,
            to_date=date(2026, 11, 20),
            reason=PostponeReason.STUCK,
        )
        db_session.add(postponement)
        await db_session.flush()

        stored = await db_session.scalar(select(TaskPostponement.reason))

        assert stored is PostponeReason.STUCK

    async def test_rejects_moving_backwards(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )

        await assert_rejected(
            db_session,
            TaskPostponement(
                task_id=task.id,
                from_date=TODAY,
                to_date=TODAY,
                reason=PostponeReason.BLOCKED,
            ),
        )

    async def test_rejects_other_without_note(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )

        await assert_rejected(db_session, _postponement(task, PostponeReason.OTHER))

    async def test_rejects_other_with_blank_note(
        self, db_session: AsyncSession
    ) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )

        await assert_rejected(
            db_session, _postponement(task, PostponeReason.OTHER, note="   ")
        )

    async def test_stores_other_with_note(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )
        db_session.add(_postponement(task, PostponeReason.OTHER, note="Sick day"))
        await db_session.flush()

        stored = await db_session.scalar(select(TaskPostponement.note))

        assert stored == "Sick day"

    async def test_allows_note_with_any_reason(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )
        db_session.add(
            _postponement(task, PostponeReason.BLOCKED, note="Waiting on Sam")
        )
        await db_session.flush()

        stored = await db_session.scalar(select(TaskPostponement.note))

        assert stored == "Waiting on Sam"

    async def test_rejects_note_over_280_chars(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )
        db_session.add(_postponement(task, PostponeReason.OTHER, note="x" * 281))

        with pytest.raises(DBAPIError):
            await db_session.flush()

    async def test_rejects_retired_reason(self, db_session: AsyncSession) -> None:
        task = await make_task(
            db_session, await make_goal(db_session, await make_user(db_session))
        )
        insert = text(
            "INSERT INTO task_postponement (id, task_id, to_date, reason) "
            "VALUES (gen_random_uuid(), :task_id, :to_date, 'too_big')"
        )

        with pytest.raises(IntegrityError):
            await db_session.execute(insert, {"task_id": task.id, "to_date": TODAY})


class TestDailyPlan:
    async def test_rejects_second_plan_same_day(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        await make_plan(db_session, user, TODAY)

        with pytest.raises(IntegrityError):
            await make_plan(db_session, user, TODAY)

    async def test_allows_same_day_for_different_users(
        self, db_session: AsyncSession
    ) -> None:
        await make_plan(db_session, await make_user(db_session), TODAY)

        plan = await make_plan(db_session, await make_user(db_session), TODAY)

        assert plan.id is not None


class TestDailyPlanItem:
    async def test_rejects_rank_above_three(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        task = await make_task(db_session, await make_goal(db_session, user))
        plan = await make_plan(db_session, user, TODAY)

        await assert_rejected(
            db_session,
            DailyPlanItem(plan_id=plan.id, task_id=task.id, user_id=user.id, rank=4),
        )

    async def test_rejects_duplicate_rank(self, db_session: AsyncSession) -> None:
        user = await make_user(db_session)
        goal = await make_goal(db_session, user)
        first, second = (
            await make_task(db_session, goal),
            await make_task(db_session, goal),
        )
        plan = await make_plan(db_session, user, TODAY)

        await assert_rejected(
            db_session,
            DailyPlanItem(plan_id=plan.id, task_id=first.id, user_id=user.id, rank=1),
            DailyPlanItem(plan_id=plan.id, task_id=second.id, user_id=user.id, rank=1),
        )

    async def test_rejects_task_owned_by_another_user(
        self, db_session: AsyncSession
    ) -> None:
        owner = await make_user(db_session)
        other = await make_user(db_session)
        task = await make_task(db_session, await make_goal(db_session, other))
        plan = await make_plan(db_session, owner, TODAY)

        await assert_rejected(
            db_session,
            DailyPlanItem(plan_id=plan.id, task_id=task.id, user_id=owner.id, rank=1),
        )
