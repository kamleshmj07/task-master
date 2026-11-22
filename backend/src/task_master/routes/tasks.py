"""Task endpoints. Every route acts only on the current user's tasks."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Select, func, select

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import SessionDep
from task_master.models import Goal, Task, TaskStatus, TaskStep, utc_now
from task_master.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_owned_or_404
from task_master.schemas import TaskCounts, TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def handle_create_task(
    body: TaskCreate, user: CurrentUserDep, session: SessionDep
) -> TaskRead:
    """Create a task with its steps, optionally under one of the user's goals."""
    if body.goal_id is not None:
        await get_owned_or_404(session, Goal, body.goal_id, user.id)
    task = Task(
        user_id=user.id,
        **body.model_dump(exclude={"steps"}),
        steps=[
            TaskStep(position=position, text=text)
            for position, text in enumerate(body.steps)
        ],
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return TaskRead.model_validate(task)


@router.get("")
async def handle_list_tasks(
    user: CurrentUserDep,
    session: SessionDep,
    goal_id: uuid.UUID | None = None,
    no_goal: bool = False,
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    someday: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TaskRead]:
    """List tasks a page at a time, with optional filters.

    Open tasks come soonest due first (Someday last); finished ones most
    recently completed first. `someday=true` lists only undated tasks,
    `someday=false` only dated ones; `no_goal=true` only goal-less ones.
    """
    statement = _owned_tasks(user.id, goal_id, no_goal)
    if task_status is not None:
        statement = statement.where(Task.status == task_status)
    if someday is not None:
        undated = Task.due_date.is_(None)
        statement = statement.where(undated if someday else ~undated)
    order = (
        (Task.completed_at.desc().nulls_last(), Task.id)
        if task_status is TaskStatus.DONE
        else (Task.due_date.asc().nulls_last(), Task.created_at, Task.id)
    )
    statement = statement.order_by(*order).limit(limit).offset(offset)
    return [TaskRead.model_validate(task) for task in await session.scalars(statement)]


@router.get("/counts")
async def handle_count_tasks(
    user: CurrentUserDep,
    session: SessionDep,
    goal_id: uuid.UUID | None = None,
    no_goal: bool = False,
) -> TaskCounts:
    """How many tasks are Scheduled, in Someday and Done, for the same filters."""
    tasks = _owned_tasks(user.id, goal_id, no_goal).subquery()
    is_open = tasks.c.status == TaskStatus.TODO
    row = (
        await session.execute(
            select(
                func.count().filter(is_open, tasks.c.due_date.is_not(None)),
                func.count().filter(is_open, tasks.c.due_date.is_(None)),
                func.count().filter(tasks.c.status == TaskStatus.DONE),
            )
        )
    ).one()
    return TaskCounts(scheduled=row[0], someday=row[1], done=row[2])


@router.get("/{task_id}")
async def handle_get_task(
    task_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> TaskRead:
    """Return one task."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    return TaskRead.model_validate(task)


@router.patch("/{task_id}")
async def handle_update_task(
    task_id: uuid.UUID, body: TaskUpdate, user: CurrentUserDep, session: SessionDep
) -> TaskRead:
    """Change a task; moving it requires owning the destination goal."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    changes = body.changes()
    _refuse_hidden_postponement(task, changes)
    if changes.get("goal_id") is not None:
        await get_owned_or_404(session, Goal, changes["goal_id"], user.id)
    for field, value in _with_completion(task, changes).items():
        setattr(task, field, value)
    await session.commit()
    await session.refresh(task)
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def handle_delete_task(
    task_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> None:
    """Delete a task."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    await session.delete(task)
    await session.commit()


def _owned_tasks(
    user_id: uuid.UUID, goal_id: uuid.UUID | None, no_goal: bool
) -> Select[Task]:
    """The user's tasks, narrowed to one goal or to goal-less ones."""
    statement = select(Task).where(Task.user_id == user_id)
    if no_goal:
        return statement.where(Task.goal_id.is_(None))
    if goal_id is not None:
        return statement.where(Task.goal_id == goal_id)
    return statement


def _with_completion(task: Task, changes: dict[str, Any]) -> dict[str, Any]:
    """Stamp `completed_at` when a task becomes done; clear it when reopened."""
    new_status = changes.get("status")
    if new_status is None or new_status == task.status:
        return changes
    completed_at = utc_now() if new_status == TaskStatus.DONE else None
    return {**changes, "completed_at": completed_at}


def _refuse_hidden_postponement(task: Task, changes: dict[str, Any]) -> None:
    """Send later or cleared due dates through `POST /tasks/{id}/postpone`.

    Clearing a date moves the task to Someday, which is a postponement too.

    Pushing a date back is a postponement: it must record a reason and count
    towards `postpone_count`. Scheduling an undated task, or bringing a date
    forward, is a plain edit.
    """
    if "due_date" not in changes or task.due_date is None:
        return
    new_date = changes["due_date"]
    if new_date is not None and new_date <= task.due_date:
        return
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Use POST /tasks/{task_id}/postpone to move a due date later or to Someday"
        ),
    )
