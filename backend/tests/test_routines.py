"""Tests for routine schedules and streaks."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from task_master.models import RoutineFrequency
from task_master.routines import (
    DayMark,
    Schedule,
    current_streak,
    is_due,
    recent_marks,
)
from task_master.schemas import RoutineCreate

START = date(2026, 1, 1)
END = date(2026, 12, 31)


def schedule(
    frequency: RoutineFrequency,
    weekdays: tuple[int, ...] = (),
    day_of_month: int | None = None,
) -> Schedule:
    return Schedule(frequency, weekdays, day_of_month, START, END)


DAILY = schedule(RoutineFrequency.DAILY)
MON_WED_FRI = schedule(RoutineFrequency.WEEKLY, weekdays=(0, 2, 4))


class TestIsDue:
    def test_daily_is_due_every_day(self) -> None:
        assert all(is_due(DAILY, START + timedelta(n)) for n in range(10))

    @pytest.mark.parametrize("day", [date(2025, 12, 31), date(2027, 1, 1)])
    def test_not_due_outside_its_dates(self, day: date) -> None:
        assert is_due(DAILY, day) is False

    def test_due_on_start_and_end_dates(self) -> None:
        assert (is_due(DAILY, START), is_due(DAILY, END)) == (True, True)

    def test_weekly_is_due_on_chosen_days(self) -> None:
        week = [date(2026, 11, 16) + timedelta(n) for n in range(7)]  # Mon..Sun

        due = [is_due(MON_WED_FRI, day) for day in week]

        assert due == [True, False, True, False, True, False, False]

    def test_monthly_is_due_on_its_day(self) -> None:
        fifteenth = schedule(RoutineFrequency.MONTHLY, day_of_month=15)

        assert (
            is_due(fifteenth, date(2026, 3, 15)),
            is_due(fifteenth, date(2026, 3, 16)),
        ) == (True, False)

    @pytest.mark.parametrize(
        ("day", "due"),
        [
            (date(2026, 2, 28), True),  # February falls back to its last day
            (date(2026, 4, 30), True),  # so do 30-day months
            (date(2026, 5, 30), False),  # 31-day months use the 31st
            (date(2026, 5, 31), True),
        ],
    )
    def test_monthly_31st_falls_back_to_last_day(self, day: date, due: bool) -> None:
        thirty_first = schedule(RoutineFrequency.MONTHLY, day_of_month=31)

        assert is_due(thirty_first, day) is due

    def test_monthly_29th_in_leap_february(self) -> None:
        leap = Schedule(
            RoutineFrequency.MONTHLY, (), 29, date(2028, 1, 1), date(2028, 12, 31)
        )

        assert (is_due(leap, date(2028, 2, 28)), is_due(leap, date(2028, 2, 29))) == (
            False,
            True,
        )


class TestCurrentStreak:
    def test_counts_consecutive_ticked_days(self) -> None:
        today = date(2026, 3, 10)
        done = {today - timedelta(n) for n in range(4)}

        assert current_streak(DAILY, done, today) == 4

    def test_unticked_today_does_not_break_it(self) -> None:
        today = date(2026, 3, 10)
        done = {today - timedelta(n) for n in range(1, 4)}

        assert current_streak(DAILY, done, today) == 3

    def test_a_missed_day_ends_it(self) -> None:
        today = date(2026, 3, 10)
        done = {today, today - timedelta(1), today - timedelta(3)}

        assert current_streak(DAILY, done, today) == 2

    def test_skips_days_the_routine_is_not_due(self) -> None:
        friday = date(2026, 11, 20)
        done = {friday, date(2026, 11, 18), date(2026, 11, 16)}  # Mon, Wed, Fri

        assert current_streak(MON_WED_FRI, done, friday + timedelta(2)) == 3

    def test_stops_at_the_start_date(self) -> None:
        done = {START + timedelta(n) for n in range(3)}

        assert current_streak(DAILY, done, START + timedelta(2)) == 3

    def test_counts_back_from_the_end_date_once_finished(self) -> None:
        done = {END, END - timedelta(1)}

        assert current_streak(DAILY, done, END + timedelta(30)) == 2

    def test_is_zero_without_ticks(self) -> None:
        assert current_streak(DAILY, set(), date(2026, 3, 10)) == 0


class TestRecentMarks:
    def test_covers_seven_days_oldest_first(self) -> None:
        today = date(2026, 3, 10)
        done = {today - timedelta(6), today}

        marks = recent_marks(DAILY, done, today, today)

        assert marks == [DONE, *[MISSED] * 5, DONE]

    def test_unticked_today_is_still_open(self) -> None:
        today = date(2026, 3, 10)

        assert recent_marks(DAILY, set(), today, today)[-1] == DayMark.OPEN

    def test_marks_days_the_routine_is_not_due(self) -> None:
        friday = date(2026, 11, 20)
        done = {date(2026, 11, 16), date(2026, 11, 18)}  # Mon, Wed

        marks = recent_marks(MON_WED_FRI, done, friday, friday)

        # Sat 14 to Fri 20.
        assert marks == [NOT_DUE, NOT_DUE, DONE, NOT_DUE, DONE, NOT_DUE, OPEN]

    def test_days_before_the_start_are_not_due(self) -> None:
        marks = recent_marks(DAILY, set(), START + timedelta(1), START + timedelta(1))

        assert marks[:5] == [NOT_DUE] * 5

    def test_future_days_are_open(self) -> None:
        today = date(2026, 3, 10)

        marks = recent_marks(DAILY, set(), today + timedelta(3), today)

        assert marks[-4:] == [OPEN] * 4


DONE, MISSED, OPEN, NOT_DUE = (
    DayMark.DONE,
    DayMark.MISSED,
    DayMark.OPEN,
    DayMark.NOT_DUE,
)


class TestRoutineCreate:
    def base(self, **fields: object) -> dict[str, object]:
        return {
            "title": "Workout",
            "frequency": "daily",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            **fields,
        }

    def test_accepts_daily(self) -> None:
        assert RoutineCreate.model_validate(self.base()).weekdays is None

    def test_sorts_and_deduplicates_weekdays(self) -> None:
        routine = RoutineCreate.model_validate(
            self.base(frequency="weekly", weekdays=[4, 0, 4])
        )

        assert routine.weekdays == [0, 4]

    @pytest.mark.parametrize(
        "fields",
        [
            {"frequency": "weekly"},
            {"frequency": "weekly", "weekdays": []},
            {"frequency": "weekly", "weekdays": [7]},
            {"frequency": "daily", "weekdays": [1]},
            {"frequency": "monthly"},
            {"frequency": "monthly", "day_of_month": 32},
            {"frequency": "daily", "day_of_month": 5},
            {"end_date": "2025-12-31"},
            {"end_date": None},
            {"frequency": "yearly"},
        ],
    )
    def test_rejects_inconsistent_schedules(self, fields: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            RoutineCreate.model_validate(self.base(**fields))

    def test_end_date_is_required(self) -> None:
        payload = self.base()
        del payload["end_date"]

        with pytest.raises(ValidationError):
            RoutineCreate.model_validate(payload)
