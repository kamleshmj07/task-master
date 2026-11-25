"""Routine endpoints: recurring items ticked off on each day they are due."""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from task_master.auth.users import CurrentUserDep
from task_master.dependencies import NowDep, SessionDep, local_today
from task_master.models import (
    Routine,
    RoutineCompletion,
    RoutineFrequency,
)
from task_master.queries import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, get_owned_or_404
from task_master.routines import Schedule, is_due, load_due_routines
from task_master.schemas import (
    DueRoutine,
    RoutineCreate,
    RoutineRead,
    RoutineSchedule,
    RoutineUpdate,
)

router = APIRouter(prefix="/routines", tags=["routines"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def handle_create_routine(
    body: RoutineCreate, user: CurrentUserDep, session: SessionDep
) -> RoutineRead:
    """Create a routine, optionally under one of the user's goals."""
    routine = Routine(user_id=user.id, **body.model_dump())
    session.add(routine)
    await session.commit()
    await session.refresh(routine)
    return RoutineRead.model_validate(routine)


@router.get("")
async def handle_list_routines(
    user: CurrentUserDep,
    session: SessionDep,
    active_on: date | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RoutineRead]:
    """List routines by title; `active_on` keeps those running on that day."""
    statement = select(Routine).where(Routine.user_id == user.id)
    if active_on is not None:
        statement = statement.where(
            Routine.start_date <= active_on, Routine.end_date >= active_on
        )
    statement = statement.order_by(Routine.title, Routine.id)
    routines = await session.scalars(statement.limit(limit).offset(offset))
    return [RoutineRead.model_validate(routine) for routine in routines]


@router.get("/due")
async def handle_list_due_routines(
    user: CurrentUserDep, session: SessionDep, now: NowDep, on: date | None = None
) -> list[DueRoutine]:
    """Routines due on `on` (default: today, in the user's timezone)."""
    today = local_today(user.timezone, now)
    due = await load_due_routines(session, user.id, on or today, today)
    return [
        DueRoutine(
            routine=RoutineRead.model_validate(r),
            done=done,
            streak=streak,
            recent_days=recent,
        )
        for r, done, streak, recent in due
    ]


@router.get("/{routine_id}")
async def handle_get_routine(
    routine_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> RoutineRead:
    """Return one routine."""
    routine = await get_owned_or_404(session, Routine, routine_id, user.id)
    return RoutineRead.model_validate(routine)


@router.patch("/{routine_id}")
async def handle_update_routine(
    routine_id: uuid.UUID,
    body: RoutineUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> RoutineRead:
    """Change a routine. Switching frequency drops details it no longer uses."""
    routine = await get_owned_or_404(session, Routine, routine_id, user.id)
    changes = body.changes()
    merged = _merged_schedule(routine, changes)
    for field, value in merged.items():
        setattr(routine, field, value)
    await session.commit()
    await session.refresh(routine)
    return RoutineRead.model_validate(routine)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def handle_delete_routine(
    routine_id: uuid.UUID, user: CurrentUserDep, session: SessionDep
) -> None:
    """Delete a routine and its history."""
    routine = await get_owned_or_404(session, Routine, routine_id, user.id)
    await session.delete(routine)
    await session.commit()


@router.put("/{routine_id}/completions/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def handle_tick_routine(
    routine_id: uuid.UUID,
    day: date,
    user: CurrentUserDep,
    session: SessionDep,
    now: NowDep,
) -> None:
    """Tick a routine off for `day`. Ticking twice is harmless."""
    routine = await get_owned_or_404(session, Routine, routine_id, user.id)
    _check_tickable(routine, day, local_today(user.timezone, now))
    await session.execute(
        insert(RoutineCompletion)
        .values(routine_id=routine.id, completed_on=day)
        .on_conflict_do_nothing()
    )
    await session.commit()


@router.delete(
    "/{routine_id}/completions/{day}", status_code=status.HTTP_204_NO_CONTENT
)
async def handle_untick_routine(
    routine_id: uuid.UUID, day: date, user: CurrentUserDep, session: SessionDep
) -> None:
    """Undo a tick for `day`."""
    routine = await get_owned_or_404(session, Routine, routine_id, user.id)
    await session.execute(
        delete(RoutineCompletion).where(
            RoutineCompletion.routine_id == routine.id,
            RoutineCompletion.completed_on == day,
        )
    )
    await session.commit()


def _check_tickable(routine: Routine, day: date, today: date) -> None:
    """Only due days that have already started can be ticked."""
    if day > today:
        raise _unprocessable("Cannot tick off a day that has not started")
    if not is_due(Schedule.of(routine), day):
        raise _unprocessable("The routine is not due on that day")


def _merged_schedule(routine: Routine, changes: dict[str, Any]) -> dict[str, Any]:
    """Apply `changes` to the routine's schedule, then check it as a whole."""
    merged: dict[str, Any] = {
        "frequency": routine.frequency,
        "weekdays": routine.weekdays,
        "day_of_month": routine.day_of_month,
        "start_date": routine.start_date,
        "end_date": routine.end_date,
        **changes,
    }
    if merged["frequency"] is not RoutineFrequency.WEEKLY:
        merged["weekdays"] = None
    if merged["frequency"] is not RoutineFrequency.MONTHLY:
        merged["day_of_month"] = None
    try:
        schedule = RoutineSchedule.model_validate(merged)
    except ValidationError as error:
        raise _unprocessable(error.errors()[0]["msg"]) from None
    return {**changes, **schedule.model_dump()}


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
    )
