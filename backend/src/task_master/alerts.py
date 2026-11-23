"""Decide which notifications a user should get, and create the missing ones.

Four events, each identified by a key so checking again never duplicates:

- an active goal's deadline is within `GOAL_DEADLINE_DAYS` (once per deadline)
- every task under an active goal is done (once per latest completion)
- an active goal has not moved for `STALE_GOAL_DAYS` (once per quiet spell)
- open tasks are due within `DUE_SOON_DAYS` (one summary a day)

The client calls the check when the app opens, so no scheduler is needed.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.dependencies import local_today
from task_master.models import (
    Goal,
    GoalStatus,
    Notification,
    NotificationKind,
    Task,
    TaskStatus,
    TaskStep,
    User,
)

GOAL_DEADLINE_DAYS = 7
STALE_GOAL_DAYS = 30
# "Next 3 days": today, tomorrow and the day after.
DUE_SOON_DAYS = 3


@dataclass(frozen=True)
class Alert:
    """A notification that should exist, before it is stored."""

    kind: NotificationKind
    key: str
    title: str
    body: str
    goal_id: uuid.UUID | None = None


async def check_notifications(session: AsyncSession, user: User, now: datetime) -> int:
    """Create any notifications the user is due; return how many are new."""
    today = local_today(user.timezone, now)
    alerts = [
        *await goal_deadline_alerts(session, user.id, today),
        *await goal_done_alerts(session, user.id),
        *await goal_stale_alerts(session, user.id, now),
        *await tasks_due_soon_alerts(session, user.id, today),
    ]
    if not alerts:
        return 0
    result = await session.execute(
        insert(Notification)
        .values(
            [
                {
                    "id": uuid.uuid4(),
                    "user_id": user.id,
                    "kind": alert.kind,
                    "key": alert.key,
                    "title": alert.title,
                    "body": alert.body,
                    "goal_id": alert.goal_id,
                    "created_at": now,
                }
                for alert in alerts
            ]
        )
        .on_conflict_do_nothing(constraint="uq_notification_user_id_key")
        .returning(Notification.id)
    )
    created = len(result.all())
    await session.commit()
    return created


async def goal_deadline_alerts(
    session: AsyncSession, user_id: uuid.UUID, today: date
) -> list[Alert]:
    """Active goals whose deadline falls within the next week."""
    goals = await session.scalars(
        select(Goal).where(
            Goal.user_id == user_id,
            Goal.status == GoalStatus.ACTIVE,
            Goal.deadline >= today,
            Goal.deadline <= today + timedelta(days=GOAL_DEADLINE_DAYS),
        )
    )
    return [
        Alert(
            kind=NotificationKind.GOAL_DEADLINE,
            key=f"goal_deadline:{goal.id}:{goal.deadline}",
            title=f"“{goal.title}” is due {_when(goal.deadline, today)}",
            body=f"The deadline is {_day(goal.deadline)}. Check what is left to do.",
            goal_id=goal.id,
        )
        for goal in goals
        if goal.deadline is not None
    ]


async def goal_done_alerts(session: AsyncSession, user_id: uuid.UUID) -> list[Alert]:
    """Active goals with tasks, every one of them done."""
    open_tasks = func.count(Task.id).filter(Task.status == TaskStatus.TODO)
    rows = await session.execute(
        select(Goal.id, Goal.title, func.max(Task.completed_at))
        .join(Task, Task.goal_id == Goal.id)
        .where(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
        .group_by(Goal.id, Goal.title)
        .having(open_tasks == 0)
    )
    return [
        Alert(
            kind=NotificationKind.GOAL_DONE,
            key=f"goal_done:{goal_id}:{last_done.isoformat() if last_done else ''}",
            title=f"Every task for “{title}” is done",
            body="Mark the goal complete, or add the next task toward it.",
            goal_id=goal_id,
        )
        for goal_id, title, last_done in rows
    ]


async def goal_stale_alerts(
    session: AsyncSession, user_id: uuid.UUID, now: datetime
) -> list[Alert]:
    """Active goals with no change, new task or progress for a while.

    A goal "moves" when it is edited, or one of its tasks is added, edited or
    finished, or one of their steps is ticked.
    """
    last_moved = func.greatest(
        Goal.updated_at,
        func.max(Task.updated_at),
        func.max(TaskStep.done_at),
    )
    rows = await session.execute(
        select(Goal.id, Goal.title, last_moved)
        .outerjoin(Task, Task.goal_id == Goal.id)
        .outerjoin(TaskStep, TaskStep.task_id == Task.id)
        .where(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
        .group_by(Goal.id, Goal.title, Goal.updated_at)
        .having(last_moved < now - timedelta(days=STALE_GOAL_DAYS))
    )
    return [
        Alert(
            kind=NotificationKind.GOAL_STALE,
            key=f"goal_stale:{goal_id}:{moved.date()}",
            title=f"“{title}” hasn't moved in {(now - moved).days} days",
            body="Add a next task, or archive the goal if it no longer matters.",
            goal_id=goal_id,
        )
        for goal_id, title, moved in rows
    ]


async def tasks_due_soon_alerts(
    session: AsyncSession, user_id: uuid.UUID, today: date
) -> list[Alert]:
    """One summary when open tasks are due in the next few days."""
    last_day = today + timedelta(days=DUE_SOON_DAYS - 1)
    count = await session.scalar(
        select(func.count(Task.id)).where(
            Task.user_id == user_id,
            Task.status == TaskStatus.TODO,
            and_(Task.due_date >= today, Task.due_date <= last_day),
        )
    )
    if not count:
        return []
    noun = "task is" if count == 1 else "tasks are"
    return [
        Alert(
            kind=NotificationKind.TASKS_DUE_SOON,
            key=f"tasks_due_soon:{today}",
            title=f"{count} {noun} due in the next {DUE_SOON_DAYS} days",
            body="Review them and make sure each has a clear next step.",
        )
    ]


def _when(day: date, today: date) -> str:
    days = (day - today).days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


def _day(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"
