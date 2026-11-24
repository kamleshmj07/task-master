"""Postponing tasks: record why, move the date, and suggest a fix."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import NowDep, SessionDep, local_today
from task_master.models import (
    PostponeReason,
    Task,
    TaskPostponement,
    TaskStatus,
)
from task_master.postponement import suggest
from task_master.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_owned_or_404
from task_master.repeats import next_run_date
from task_master.schemas import (
    PostponementRead,
    PostponeRequest,
    PostponeResponse,
    SkipRequest,
    SuggestionRead,
    TaskRead,
)

router = APIRouter(prefix="/tasks", tags=["postponements"])


@router.post("/{task_id}/postpone", status_code=status.HTTP_201_CREATED)
async def handle_postpone_task(
    task_id: uuid.UUID,
    body: PostponeRequest,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
) -> PostponeResponse:
    """Move an open task later or to Someday; get a fix for the reason given."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    _check_postponable(task, body, local_today(user.timezone, now))
    return await _postpone(session, task, body.to_date, body.reason, body.note)


@router.post("/{task_id}/skip", status_code=status.HTTP_201_CREATED)
async def handle_skip_run(
    task_id: uuid.UUID,
    body: SkipRequest,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
) -> PostponeResponse:
    """Skip a repeating task's run: it moves to the next due day.

    A skip asks why, like any postponement, and counts as one.
    """
    task = await get_owned_or_404(session, Task, task_id, user.id)
    if task.status is TaskStatus.DONE or task.repeat_frequency is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an open run of a repeating task can be skipped",
        )
    to_date = next_run_date(task, local_today(user.timezone, now))
    if to_date is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This is the last run; there is no later one to skip to",
        )
    return await _postpone(session, task, to_date, body.reason, body.note)


async def _postpone(
    session: SessionDep,
    task: Task,
    to_date: date | None,
    reason: PostponeReason,
    note: str | None,
) -> PostponeResponse:
    """Record the postponement, move the task, and suggest a fix."""
    postponement = TaskPostponement(
        task_id=task.id,
        from_date=task.due_date,
        to_date=to_date,
        reason=reason,
        note=note,
    )
    session.add(postponement)
    # Increment in SQL so concurrent postponements are all counted.
    await session.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(due_date=to_date, postpone_count=Task.postpone_count + 1)
    )
    await session.commit()
    await session.refresh(task)
    await session.refresh(postponement)
    blocked_count = await _count_blocked(session, task.id)
    # The tip is shown once and dismissed; it is deliberately not stored.
    suggestion = suggest(reason, blocked_count)
    return PostponeResponse(
        task=TaskRead.model_validate(task),
        postponement=PostponementRead.model_validate(postponement),
        suggestion=SuggestionRead.model_validate(suggestion),
    )


@router.get("/{task_id}/postponements")
async def handle_list_postponements(
    task_id: uuid.UUID,
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PostponementRead]:
    """A task's postponement history, oldest first."""
    await get_owned_or_404(session, Task, task_id, user.id)
    statement = (
        select(TaskPostponement)
        .where(TaskPostponement.task_id == task_id)
        .order_by(
            TaskPostponement.created_at,
            TaskPostponement.to_date.asc().nulls_last(),
            TaskPostponement.id,
        )
        .limit(limit)
        .offset(offset)
    )
    rows = await session.scalars(statement)
    return [PostponementRead.model_validate(row) for row in rows]


def _check_postponable(task: Task, body: PostponeRequest, today: date) -> None:
    """Refuse finished tasks and moves that do not push the task back."""
    if task.status is TaskStatus.DONE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A finished task cannot be postponed",
        )
    if body.to_date is None:
        if task.due_date is None:
            raise _unprocessable("The task is already in Someday")
        if task.repeat_frequency is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A repeating task cannot go to Someday; skip the run instead",
            )
        return
    if body.to_date < today:
        raise _unprocessable("Cannot postpone into the past")
    if task.due_date is not None and body.to_date <= task.due_date:
        raise _unprocessable("The new date must be after the current due date")


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
    )


async def _count_blocked(session: SessionDep, task_id: uuid.UUID) -> int:
    """How many times this task has been postponed as blocked."""
    statement = select(func.count()).where(
        TaskPostponement.task_id == task_id,
        TaskPostponement.reason == PostponeReason.BLOCKED,
    )
    return await session.scalar(statement) or 0
