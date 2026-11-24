"""Repeating tasks: one run is open at a time; finishing it creates the next.

A repeating task is recurring goal work ("Run 20 min every day"). Each run is
an ordinary task with its own steps, time limit and postponements. The runs
of one series share a `series_id` and the same repeat rule.
"""

from datetime import date, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from task_master.models import Task, TaskStatus, TaskStep
from task_master.routines import Schedule, is_due

# A monthly rule always has a run within this many days; bounds the search.
MAX_SEARCH_DAYS = 400


def schedule_of(task: Task) -> Schedule | None:
    """The schedule a repeating task's runs follow, from its current run on."""
    if task.repeat_frequency is None or task.due_date is None:
        return None
    return Schedule(
        frequency=task.repeat_frequency,
        weekdays=tuple(task.repeat_weekdays or ()),
        day_of_month=task.repeat_day_of_month,
        start_date=task.due_date,
        end_date=task.repeat_until or date.max,
    )


def next_run_date(task: Task, today: date) -> date | None:
    """The first due day after this run that is not in the past.

    Runs missed while this one was open are not owed: finishing or skipping
    an overdue run moves on to today, or the next due day after it.
    """
    schedule = schedule_of(task)
    if schedule is None or task.due_date is None:
        return None
    day = max(task.due_date + timedelta(days=1), today)
    for _ in range(MAX_SEARCH_DAYS):
        if day > schedule.end_date:
            return None
        if is_due(schedule, day):
            return day
        day += timedelta(days=1)
    return None


async def create_next_run(session: AsyncSession, task: Task, today: date) -> None:
    """Add the series' next run after `task` is finished, if one is due.

    Nothing is added while another run of the series is still open, so
    reopening and finishing a run again never doubles up.
    """
    due = next_run_date(task, today)
    if due is None or await _has_other_open_run(session, task):
        return
    session.add(
        Task(
            user_id=task.user_id,
            goal_id=task.goal_id,
            title=task.title,
            time_limit_minutes=task.time_limit_minutes,
            due_date=due,
            repeat_frequency=task.repeat_frequency,
            repeat_weekdays=task.repeat_weekdays,
            repeat_day_of_month=task.repeat_day_of_month,
            repeat_until=task.repeat_until,
            series_id=task.series_id,
            steps=[
                TaskStep(position=position, text=step.text)
                for position, step in enumerate(task.steps)
            ],
        )
    )


async def _has_other_open_run(session: AsyncSession, task: Task) -> bool:
    other_open = exists().where(
        Task.series_id == task.series_id,
        Task.id != task.id,
        Task.status == TaskStatus.TODO,
    )
    return bool(await session.scalar(select(other_open)))
