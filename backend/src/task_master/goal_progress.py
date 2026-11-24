"""Goal progress: task counts, the next task due, and last movement.

Loaded for many goals in a handful of queries, never one query per goal.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, DateTime, Select, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import Goal, Task, TaskStatus, TaskStep
from task_master.schemas import GoalProgress, GoalRead, GoalSummary, NextDueTask


def last_moved() -> ColumnElement[datetime]:
    """When a goal last moved: it was edited, a task changed, or a step was ticked.

    Use with `Goal` outer-joined to its tasks and their steps, grouped by goal.
    """
    return func.greatest(
        Goal.updated_at,
        func.max(Task.updated_at),
        func.max(TaskStep.done_at),
        type_=DateTime(timezone=True),
    )


def with_last_moved[*Ts](statement: Select[*Ts]) -> Select[*Ts]:
    """Join a goal query to the tasks and steps that `last_moved` reads."""
    return statement.outerjoin(Task, Task.goal_id == Goal.id).outerjoin(
        TaskStep, TaskStep.task_id == Task.id
    )


async def read_goals(session: AsyncSession, goals: Sequence[Goal]) -> list[GoalRead]:
    """Goals as returned by the API, each with its progress."""
    progress = await load_progress(session, [goal.id for goal in goals])
    return [
        GoalRead(
            **GoalSummary.model_validate(goal).model_dump(), progress=progress[goal.id]
        )
        for goal in goals
    ]


async def load_progress(
    session: AsyncSession, goal_ids: list[uuid.UUID]
) -> dict[uuid.UUID, GoalProgress]:
    """Progress for each goal in `goal_ids`."""
    if not goal_ids:
        return {}
    counts = await _task_counts(session, goal_ids)
    next_due = await _next_due(session, goal_ids)
    moved = await _last_moved(session, goal_ids)
    return {
        goal_id: GoalProgress(
            total_tasks=counts.get(goal_id, (0, 0))[0],
            done_tasks=counts.get(goal_id, (0, 0))[1],
            next_due_task=next_due.get(goal_id),
            last_moved_at=moved[goal_id],
        )
        for goal_id in goal_ids
    }


async def _task_counts(
    session: AsyncSession, goal_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    rows = await session.execute(
        select(
            Task.goal_id,
            func.count(Task.id),
            func.count(Task.id).filter(Task.status == TaskStatus.DONE),
        )
        .where(Task.goal_id.in_(goal_ids))
        .group_by(Task.goal_id)
    )
    return {goal_id: (total, done) for goal_id, total, done in rows if goal_id}


async def _next_due(
    session: AsyncSession, goal_ids: list[uuid.UUID]
) -> dict[uuid.UUID, NextDueTask]:
    """The soonest-due open task per goal (Postgres DISTINCT ON)."""
    rows = await session.execute(
        select(Task.goal_id, Task.id, Task.title, Task.due_date)
        .where(
            Task.goal_id.in_(goal_ids),
            Task.status == TaskStatus.TODO,
            Task.due_date.is_not(None),
        )
        .order_by(Task.goal_id, Task.due_date, Task.created_at, Task.id)
        .ext(distinct_on(Task.goal_id))
    )
    return {
        goal_id: NextDueTask(id=task_id, title=title, due_date=due_date)
        for goal_id, task_id, title, due_date in rows
        if goal_id and due_date
    }


async def _last_moved(
    session: AsyncSession, goal_ids: list[uuid.UUID]
) -> dict[uuid.UUID, datetime]:
    statement = with_last_moved(select(Goal.id, last_moved()))
    rows = await session.execute(
        statement.where(Goal.id.in_(goal_ids)).group_by(Goal.id, Goal.updated_at)
    )
    return {goal_id: moved for goal_id, moved in rows}
