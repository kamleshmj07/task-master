"""Goal endpoints. Every route acts only on the current user's goals."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import SessionDep
from task_master.goal_progress import read_goals
from task_master.models import Goal, GoalStatus
from task_master.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_owned_or_404
from task_master.schemas import GoalCreate, GoalRead, GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def handle_create_goal(
    body: GoalCreate, user: CurrentUserDep, session: SessionDep
) -> GoalRead:
    """Create a goal."""
    goal = Goal(user_id=user.id, **body.model_dump())
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    return (await read_goals(session, [goal]))[0]


@router.get("")
async def handle_list_goals(
    user: CurrentUserDep,
    session: SessionDep,
    goal_status: Annotated[GoalStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[GoalRead]:
    """List goals with their progress, oldest first, optionally by status."""
    statement = select(Goal).where(Goal.user_id == user.id)
    if goal_status is not None:
        statement = statement.where(Goal.status == goal_status)
    statement = statement.order_by(Goal.created_at, Goal.id).limit(limit)
    goals = (await session.scalars(statement.offset(offset))).all()
    return await read_goals(session, goals)


@router.get("/{goal_id}")
async def handle_get_goal(
    goal_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> GoalRead:
    """Return one goal with its progress."""
    goal = await get_owned_or_404(session, Goal, goal_id, user.id)
    return (await read_goals(session, [goal]))[0]


@router.patch("/{goal_id}")
async def handle_update_goal(
    goal_id: uuid.UUID, body: GoalUpdate, user: CurrentUserDep, session: SessionDep
) -> GoalRead:
    """Change any of a goal's fields."""
    goal = await get_owned_or_404(session, Goal, goal_id, user.id)
    for field, value in body.changes().items():
        setattr(goal, field, value)
    await session.commit()
    await session.refresh(goal)
    return (await read_goals(session, [goal]))[0]


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def handle_delete_goal(
    goal_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> None:
    """Delete a goal and, by cascade, its tasks and routines."""
    goal = await get_owned_or_404(session, Goal, goal_id, user.id)
    await session.delete(goal)
    await session.commit()
