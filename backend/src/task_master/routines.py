"""When routines are due, and how long their streaks are."""

import calendar
import uuid
from collections import defaultdict
from collections.abc import Set
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import Routine, RoutineCompletion, RoutineFrequency

# Streaks are counted back at most this far, to bound the work per request.
MAX_STREAK_LOOKBACK_DAYS = 3 * 366


@dataclass(frozen=True)
class Schedule:
    """The fields that decide when a routine is due."""

    frequency: RoutineFrequency
    weekdays: tuple[int, ...]
    day_of_month: int | None
    start_date: date
    end_date: date

    @classmethod
    def of(cls, routine: Routine) -> Schedule:
        """The schedule of a stored routine."""
        return cls(
            frequency=routine.frequency,
            weekdays=tuple(routine.weekdays or ()),
            day_of_month=routine.day_of_month,
            start_date=routine.start_date,
            end_date=routine.end_date,
        )


def is_due(schedule: Schedule, day: date) -> bool:
    """Whether the routine should be done on `day`.

    Monthly routines on the 29th-31st fall back to the last day of shorter
    months, so they happen every month.
    """
    if not schedule.start_date <= day <= schedule.end_date:
        return False
    match schedule.frequency:
        case RoutineFrequency.DAILY:
            return True
        case RoutineFrequency.WEEKLY:
            return day.weekday() in schedule.weekdays
        case RoutineFrequency.MONTHLY:
            return day.day == _monthly_day(schedule, day)


def current_streak(schedule: Schedule, done_on: Set[date], today: date) -> int:
    """Consecutive due days ticked off, counting back from `today`.

    An unticked `today` does not break the streak: the day is not over yet.
    """
    streak = 0
    day = min(today, schedule.end_date)
    earliest = max(schedule.start_date, today - timedelta(MAX_STREAK_LOOKBACK_DAYS))
    while day >= earliest:
        if is_due(schedule, day):
            if day in done_on:
                streak += 1
            elif day != today:
                break
        day -= timedelta(days=1)
    return streak


class DayMark(StrEnum):
    """How a routine went on one day."""

    DONE = "done"
    MISSED = "missed"  # due, not ticked, and the day is over
    OPEN = "open"  # due, not ticked yet, today or later
    NOT_DUE = "not_due"


RECENT_DAYS = 7


def recent_marks(
    schedule: Schedule, done_on: Set[date], day: date, today: date
) -> list[DayMark]:
    """The routine's last `RECENT_DAYS` days up to `day`, oldest first."""
    first = day - timedelta(RECENT_DAYS - 1)
    return [
        _mark(schedule, done_on, first + timedelta(offset), today)
        for offset in range(RECENT_DAYS)
    ]


def _mark(schedule: Schedule, done_on: Set[date], day: date, today: date) -> DayMark:
    if day in done_on:
        return DayMark.DONE
    if not is_due(schedule, day):
        return DayMark.NOT_DUE
    return DayMark.MISSED if day < today else DayMark.OPEN


def _monthly_day(schedule: Schedule, day: date) -> int:
    last_day = calendar.monthrange(day.year, day.month)[1]
    return min(schedule.day_of_month or 1, last_day)


async def load_due_routines(
    session: AsyncSession, user_id: uuid.UUID, day: date, today: date
) -> list[tuple[Routine, bool, int, list[DayMark]]]:
    """The user's routines due on `day`.

    Each comes with whether it was done on `day`, its streak, and how its
    last few days up to `day` went.
    """
    statement = (
        select(Routine)
        .where(
            Routine.user_id == user_id,
            Routine.start_date <= day,
            Routine.end_date >= day,
        )
        .order_by(Routine.title, Routine.id)
    )
    candidates = (await session.scalars(statement)).all()
    due = [routine for routine in candidates if is_due(Schedule.of(routine), day)]
    done_by_routine = await _completions(session, [r.id for r in due], today)
    return [
        (
            routine,
            day in done_by_routine[routine.id],
            current_streak(Schedule.of(routine), done_by_routine[routine.id], today),
            recent_marks(Schedule.of(routine), done_by_routine[routine.id], day, today),
        )
        for routine in due
    ]


async def _completions(
    session: AsyncSession, routine_ids: list[uuid.UUID], today: date
) -> defaultdict[uuid.UUID, set[date]]:
    """Tick-off dates per routine within the streak lookback window."""
    done: defaultdict[uuid.UUID, set[date]] = defaultdict(set)
    if not routine_ids:
        return done
    earliest = today - timedelta(MAX_STREAK_LOOKBACK_DAYS)
    rows = await session.execute(
        select(RoutineCompletion.routine_id, RoutineCompletion.completed_on).where(
            RoutineCompletion.routine_id.in_(routine_ids),
            RoutineCompletion.completed_on >= earliest,
        )
    )
    for routine_id, completed_on in rows:
        done[routine_id].add(completed_on)
    return done
