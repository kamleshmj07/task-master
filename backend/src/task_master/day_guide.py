"""What the Today page offers beside the Top 3: suggestions and heads-up.

Suggestions help pick the day's three: tasks left from the day before, then
overdue ones, then those due that day, then the next task of the goals that
have been quiet longest. Heads-up lists what needs a decision today:
overdue tasks, tasks with every step done, and tasks due within a few days.
Tasks already in the day's three appear in neither.
"""

import uuid
from collections.abc import Collection, Iterable
from datetime import date, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from task_master.goal_progress import last_moved, with_last_moved
from task_master.models import (
    DailyPlan,
    DailyPlanItem,
    Goal,
    GoalStatus,
    Task,
    TaskStatus,
    TaskStep,
)
from task_master.schemas import (
    HeadsUpItem,
    HeadsUpKind,
    PlanSuggestion,
    SuggestionKind,
    TaskRead,
)

MAX_SUGGESTIONS = 6
MAX_HEADS_UP = 5
DUE_SOON_DAYS = 3
# Goals looked at for a "next for this goal" suggestion, quietest first.
GOALS_TO_SUGGEST = 2


async def load_suggestions(
    session: AsyncSession,
    user_id: uuid.UUID,
    plan_date: date,
    today: date,
    planned: Collection[uuid.UUID],
) -> list[PlanSuggestion]:
    """Up to `MAX_SUGGESTIONS` tasks to pick from, most pressing first."""
    suggestions: list[PlanSuggestion] = []
    seen = set(planned)

    def offer(kind: SuggestionKind, tasks: Iterable[Task], **extra: object) -> None:
        for task in tasks:
            if task.id in seen or len(suggestions) >= MAX_SUGGESTIONS:
                continue
            seen.add(task.id)
            suggestions.append(
                PlanSuggestion.model_validate(
                    {"kind": kind, "task": TaskRead.model_validate(task)} | extra
                )
            )

    for rank, task in await _left_from(session, user_id, plan_date - timedelta(1)):
        offer(SuggestionKind.LEFT_OVER, [task], previous_rank=rank)
    offer(
        SuggestionKind.OVERDUE,
        await _open_tasks(session, user_id, _overdue(today), Task.due_date),
    )
    offer(
        SuggestionKind.DUE_TODAY,
        await _open_tasks(session, user_id, Task.due_date == plan_date, Task.title),
    )
    for goal, task in await _next_for_quiet_goals(session, user_id, seen):
        offer(SuggestionKind.GOAL_NEXT, [task], goal_title=goal.title)
    return suggestions


async def load_heads_up(
    session: AsyncSession,
    user_id: uuid.UUID,
    today: date,
    planned: Collection[uuid.UUID],
) -> list[HeadsUpItem]:
    """Up to `MAX_HEADS_UP` open tasks that need a decision, most urgent first."""
    groups = [
        (HeadsUpKind.OVERDUE, _overdue(today), Task.due_date),
        (HeadsUpKind.READY, _every_step_done(), Task.updated_at),
        (
            HeadsUpKind.DUE_SOON,
            Task.due_date.between(today, today + timedelta(DUE_SOON_DAYS)),
            Task.due_date,
        ),
    ]
    items: list[HeadsUpItem] = []
    seen = set(planned)
    for kind, condition, order in groups:
        for task in await _open_tasks(session, user_id, condition, order):
            if task.id in seen or len(items) >= MAX_HEADS_UP:
                continue
            seen.add(task.id)
            items.append(HeadsUpItem(kind=kind, task=TaskRead.model_validate(task)))
    return items


def _overdue(today: date) -> ColumnElement[bool]:
    return and_(Task.due_date.is_not(None), Task.due_date < today)


def _every_step_done() -> ColumnElement[bool]:
    return ~exists().where(TaskStep.task_id == Task.id, TaskStep.done_at.is_(None))


async def _open_tasks(
    session: AsyncSession,
    user_id: uuid.UUID,
    condition: ColumnElement[bool],
    order: InstrumentedAttribute[Any],
) -> list[Task]:
    statement: Select[Task] = (
        select(Task)
        .where(Task.user_id == user_id, Task.status == TaskStatus.TODO, condition)
        .order_by(order, Task.id)
        .limit(MAX_SUGGESTIONS + 3)
    )
    return list(await session.scalars(statement))


async def _left_from(
    session: AsyncSession, user_id: uuid.UUID, day: date
) -> list[tuple[int, Task]]:
    """The previous day's Top 3 tasks still open, by their rank that day."""
    rows = await session.execute(
        select(DailyPlanItem.rank, Task)
        .join(DailyPlan, DailyPlan.id == DailyPlanItem.plan_id)
        .join(Task, Task.id == DailyPlanItem.task_id)
        .where(
            DailyPlan.user_id == user_id,
            DailyPlan.plan_date == day,
            Task.status == TaskStatus.TODO,
        )
        .order_by(DailyPlanItem.rank)
    )
    return [(rank, task) for rank, task in rows]


async def _next_for_quiet_goals(
    session: AsyncSession, user_id: uuid.UUID, skip: Collection[uuid.UUID]
) -> list[tuple[Goal, Task]]:
    """The next open task of each active goal, quietest goal first."""
    goals = await session.scalars(
        with_last_moved(select(Goal))
        .where(Goal.user_id == user_id, Goal.status == GoalStatus.ACTIVE)
        .group_by(Goal.id)
        .order_by(last_moved(), Goal.id)
    )
    found: list[tuple[Goal, Task]] = []
    for goal in goals:
        task = await session.scalar(
            select(Task)
            .where(
                Task.goal_id == goal.id,
                Task.status == TaskStatus.TODO,
                Task.id.not_in(skip),
            )
            .order_by(Task.due_date.asc().nulls_last(), Task.created_at, Task.id)
            .limit(1)
        )
        if task is not None:
            found.append((goal, task))
        if len(found) >= GOALS_TO_SUGGEST:
            break
    return found
