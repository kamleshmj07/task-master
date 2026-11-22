"""Daily plan endpoints: the Top 3 tasks for a day, beside its routines."""

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import delete, select

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import NowDep, SessionDep, local_today
from task_master.models import (
    DailyPlan,
    DailyPlanItem,
    Task,
    TaskStatus,
    User,
)
from task_master.routines import load_due_routines
from task_master.schemas import (
    DueRoutine,
    PlanItem,
    PlanRead,
    PlanUpdate,
    RoutineRead,
    TaskRead,
)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/{plan_date}")
async def handle_get_plan(
    plan_date: date, user: CurrentUserDep, session: SessionDep, now: NowDep
) -> PlanRead:
    """The day's Top 3 tasks and, separately, its routines."""
    today = local_today(user.timezone, now)
    return await _read_plan(session, user, plan_date, today)


@router.put("/{plan_date}")
async def handle_set_plan(
    plan_date: date,
    body: PlanUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
) -> PlanRead:
    """Replace the day's Top 3 with `task_ids`, most important first.

    Only open tasks can join the Top 3; tasks finished while already in it
    may stay. Past days cannot be re-planned.
    """
    today = local_today(user.timezone, now)
    if plan_date < today:
        raise _unprocessable("Cannot plan a day that has passed")
    plan = await _get_or_create_plan(session, user, plan_date)
    current = set(
        await session.scalars(
            select(DailyPlanItem.task_id).where(DailyPlanItem.plan_id == plan.id)
        )
    )
    tasks = await _owned_tasks(session, user, body)
    for task in tasks:
        if task.status is TaskStatus.DONE and task.id not in current:
            raise _unprocessable("A finished task cannot join the Top 3")
    await session.execute(delete(DailyPlanItem).where(DailyPlanItem.plan_id == plan.id))
    session.add_all(
        DailyPlanItem(plan_id=plan.id, task_id=task.id, user_id=user.id, rank=rank)
        for rank, task in enumerate(tasks, start=1)
    )
    await session.commit()
    return await _read_plan(session, user, plan_date, today)


async def _read_plan(
    session: SessionDep, user: User, plan_date: date, today: date
) -> PlanRead:
    """Assemble the Top 3 and the due routines."""
    rows = await session.execute(
        select(DailyPlanItem.rank, Task)
        .join(DailyPlan, DailyPlan.id == DailyPlanItem.plan_id)
        .join(Task, Task.id == DailyPlanItem.task_id)
        .where(DailyPlan.user_id == user.id, DailyPlan.plan_date == plan_date)
        .order_by(DailyPlanItem.rank)
    )
    top_three = [
        PlanItem(rank=rank, task=TaskRead.model_validate(task)) for rank, task in rows
    ]
    routines = [
        DueRoutine(routine=RoutineRead.model_validate(r), done=done, streak=streak)
        for r, done, streak in await load_due_routines(
            session, user.id, plan_date, today
        )
    ]
    return PlanRead(plan_date=plan_date, top_three=top_three, routines=routines)


async def _get_or_create_plan(
    session: SessionDep, user: User, plan_date: date
) -> DailyPlan:
    plan = await session.scalar(
        select(DailyPlan).where(
            DailyPlan.user_id == user.id, DailyPlan.plan_date == plan_date
        )
    )
    if plan is not None:
        return plan
    plan = DailyPlan(user_id=user.id, plan_date=plan_date)
    session.add(plan)
    await session.flush()
    return plan


async def _owned_tasks(session: SessionDep, user: User, body: PlanUpdate) -> list[Task]:
    """The requested tasks in request order; 404 if any is not the user's."""
    found = {
        task.id: task
        for task in await session.scalars(
            select(Task).where(Task.id.in_(body.task_ids), Task.user_id == user.id)
        )
    }
    if len(found) != len(body.task_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    return [found[task_id] for task_id in body.task_ids]


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
    )
