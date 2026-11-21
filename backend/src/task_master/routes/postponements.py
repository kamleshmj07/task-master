"""Postponing tasks: record why, move the date, and suggest a fix."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select, update

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import SessionDep
from task_master.models import (
    PostponeReason,
    Task,
    TaskPostponement,
    TaskStatus,
    User,
    utc_now,
)
from task_master.postponement import local_today, suggest
from task_master.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_owned_or_404
from task_master.schemas import (
    PostponementRead,
    PostponeRequest,
    PostponeResponse,
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
) -> PostponeResponse:
    """Move an open task to a later date and get a fix for the reason given."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    _check_postponable(task, body, user)
    postponement = TaskPostponement(
        task_id=task.id,
        from_date=task.due_date,
        to_date=body.to_date,
        reason=body.reason,
        note=body.note,
    )
    session.add(postponement)
    # Increment in SQL so concurrent postponements are all counted.
    await session.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(due_date=body.to_date, postpone_count=Task.postpone_count + 1)
    )
    await session.commit()
    await session.refresh(task)
    await session.refresh(postponement)
    blocked_count = await _count_blocked(session, task.id)
    return PostponeResponse(
        task=TaskRead.model_validate(task),
        postponement=PostponementRead.model_validate(postponement),
        suggestion=SuggestionRead.model_validate(suggest(body.reason, blocked_count)),
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
        .order_by(TaskPostponement.to_date, TaskPostponement.id)
        .limit(limit)
        .offset(offset)
    )
    rows = await session.scalars(statement)
    return [PostponementRead.model_validate(row) for row in rows]


def _check_postponable(task: Task, body: PostponeRequest, user: User) -> None:
    """Refuse finished tasks and dates that do not move the task forward."""
    if task.status is TaskStatus.DONE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A finished task cannot be postponed",
        )
    if body.to_date < local_today(user.timezone, utc_now()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Cannot postpone into the past",
        )
    if task.due_date is not None and body.to_date <= task.due_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The new date must be after the current due date",
        )


async def _count_blocked(session: SessionDep, task_id: uuid.UUID) -> int:
    """How many times this task has been postponed as blocked."""
    statement = select(func.count()).where(
        TaskPostponement.task_id == task_id,
        TaskPostponement.reason == PostponeReason.BLOCKED,
    )
    return await session.scalar(statement) or 0
