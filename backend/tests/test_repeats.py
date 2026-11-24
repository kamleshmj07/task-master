"""Unit tests for when a repeating task's next run falls."""

from datetime import date

from task_master.models import RoutineFrequency, Task
from task_master.repeats import next_run_date

SUNDAY = date(2026, 11, 22)


def run(
    due: date | None,
    frequency: RoutineFrequency | None,
    *,
    weekdays: list[int] | None = None,
    day_of_month: int | None = None,
    until: date | None = None,
) -> Task:
    """An unsaved run of a repeating task."""
    return Task(
        title="Run 20 min",
        due_date=due,
        repeat_frequency=frequency,
        repeat_weekdays=weekdays,
        repeat_day_of_month=day_of_month,
        repeat_until=until,
    )


class TestNextRunDate:
    def test_daily_moves_to_the_next_day(self) -> None:
        task = run(SUNDAY, RoutineFrequency.DAILY)

        assert next_run_date(task, today=SUNDAY) == date(2026, 11, 23)

    def test_weekly_moves_to_the_next_chosen_weekday(self) -> None:
        task = run(SUNDAY, RoutineFrequency.WEEKLY, weekdays=[3])

        assert next_run_date(task, today=SUNDAY) == date(2026, 11, 26)

    def test_monthly_falls_back_to_the_last_day_of_short_months(self) -> None:
        task = run(date(2027, 1, 31), RoutineFrequency.MONTHLY, day_of_month=31)

        assert next_run_date(task, today=date(2027, 1, 31)) == date(2027, 2, 28)

    def test_missed_runs_are_not_owed(self) -> None:
        task = run(date(2026, 11, 18), RoutineFrequency.DAILY)

        assert next_run_date(task, today=SUNDAY) == SUNDAY

    def test_none_after_the_last_day(self) -> None:
        task = run(SUNDAY, RoutineFrequency.DAILY, until=SUNDAY)

        assert next_run_date(task, today=SUNDAY) is None

    def test_none_for_an_undated_task(self) -> None:
        task = run(None, RoutineFrequency.DAILY)

        assert next_run_date(task, today=SUNDAY) is None

    def test_none_for_a_one_off_task(self) -> None:
        task = run(SUNDAY, None)

        assert next_run_date(task, today=SUNDAY) is None
