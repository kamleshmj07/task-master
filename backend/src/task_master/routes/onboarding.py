"""First-run setup ("Light the lamp"): four steps, read from the user's data.

A step is done once the user has made the thing it asks for: a goal of their
own (not the default Essentials), a task, a Top 3 for any day, a routine.
Progress is never stored; only finishing is, so the card is gone for good.
"""

from fastapi import APIRouter
from sqlalchemy import select

from task_master.auth.users import CurrentUserDep
from task_master.defaults import DEFAULT_GOAL_TITLE
from task_master.dependencies import NowDep, SessionDep
from task_master.models import DailyPlanItem, Goal, Routine, Task, TaskStep
from task_master.schemas import (
    OnboardingGoal,
    OnboardingRead,
    OnboardingRoutine,
    OnboardingTask,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("")
async def handle_get_onboarding(
    user: CurrentUserDep, session: SessionDep
) -> OnboardingRead:
    """Which setup steps are done, with what each one made."""
    goal = await session.scalar(
        select(Goal)
        .where(Goal.user_id == user.id, Goal.title != DEFAULT_GOAL_TITLE)
        .order_by(Goal.created_at, Goal.id)
        .limit(1)
    )
    task = await session.scalar(
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(Task.created_at, Task.id)
        .limit(1)
    )
    first_step = (
        await session.scalar(
            select(TaskStep.text)
            .where(TaskStep.task_id == task.id)
            .order_by(TaskStep.position, TaskStep.id)
            .limit(1)
        )
        if task is not None
        else None
    )
    planned = await session.scalar(
        select(DailyPlanItem.task_id).where(DailyPlanItem.user_id == user.id).limit(1)
    )
    routine = await session.scalar(
        select(Routine)
        .where(Routine.user_id == user.id)
        .order_by(Routine.created_at, Routine.id)
        .limit(1)
    )
    return OnboardingRead(
        goal=OnboardingGoal(id=goal.id, title=goal.title) if goal else None,
        task=(
            OnboardingTask(id=task.id, title=task.title, first_step=first_step)
            if task
            else None
        ),
        three=planned is not None,
        routine=OnboardingRoutine(id=routine.id, title=routine.title)
        if routine
        else None,
        finished=user.onboarded_at is not None,
    )


@router.post("/finish")
async def handle_finish_onboarding(
    user: CurrentUserDep, session: SessionDep, now: NowDep
) -> OnboardingRead:
    """Mark setup as finished, so the card never shows again."""
    if user.onboarded_at is None:
        user.onboarded_at = now
        await session.commit()
    return await handle_get_onboarding(user, session)
