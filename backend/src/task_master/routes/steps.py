"""Task step endpoints. Each returns the whole task, so clients redraw once."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import NowDep, SessionDep
from task_master.models import Task, TaskStep
from task_master.queries import get_owned_or_404
from task_master.schemas import (
    MAX_STEPS,
    StepCreate,
    StepOrder,
    StepUpdate,
    TaskRead,
)

router = APIRouter(prefix="/tasks/{task_id}/steps", tags=["steps"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def handle_add_step(
    task_id: uuid.UUID, body: StepCreate, user: CurrentUserDep, session: SessionDep
) -> TaskRead:
    """Add a step to the end of a task."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    if len(task.steps) >= MAX_STEPS:
        raise _unprocessable(f"A task can have at most {MAX_STEPS} steps")
    last = await session.scalar(
        select(func.max(TaskStep.position)).where(TaskStep.task_id == task.id)
    )
    task.steps.append(TaskStep(position=(last or 0) + 1, text=body.text))
    return await _saved(session, task)


@router.put("/order")
async def handle_reorder_steps(
    task_id: uuid.UUID, body: StepOrder, user: CurrentUserDep, session: SessionDep
) -> TaskRead:
    """Put the task's steps in the given order; every step must be listed once."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    by_id = {step.id: step for step in task.steps}
    if len(body.step_ids) != len(by_id) or set(body.step_ids) != set(by_id):
        raise _unprocessable("List every step of the task exactly once")
    for position, step_id in enumerate(body.step_ids):
        by_id[step_id].position = position
    await session.commit()
    session.expire(task, ["steps"])
    await session.refresh(task)
    return TaskRead.model_validate(task)


@router.patch("/{step_id}")
async def handle_update_step(
    task_id: uuid.UUID,
    step_id: uuid.UUID,
    body: StepUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
) -> TaskRead:
    """Rename a step or tick it off. Ticking never completes the task itself."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    step = _step_of(task, step_id)
    changes = body.changes()
    if "text" in changes:
        step.text = changes["text"]
    if "done" in changes and changes["done"] != (step.done_at is not None):
        step.done_at = now if changes["done"] else None
    return await _saved(session, task)


@router.delete("/{step_id}")
async def handle_delete_step(
    task_id: uuid.UUID, step_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> TaskRead:
    """Remove a step. A task always keeps at least one."""
    task = await get_owned_or_404(session, Task, task_id, user.id)
    step = _step_of(task, step_id)
    if len(task.steps) == 1:
        raise _unprocessable("A task needs at least one step")
    task.steps.remove(step)
    return await _saved(session, task)


def _step_of(task: Task, step_id: uuid.UUID) -> TaskStep:
    step = next((step for step in task.steps if step.id == step_id), None)
    if step is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Step not found"
        )
    return step


async def _saved(session: SessionDep, task: Task) -> TaskRead:
    await session.commit()
    await session.refresh(task)
    return TaskRead.model_validate(task)


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
    )
