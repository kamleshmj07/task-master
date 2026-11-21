"""Tests for account schema validation."""

import pytest
from pydantic import ValidationError

from task_master.auth.schemas import UserCreate, UserUpdate

EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"


class TestUserCreate:
    def test_defaults_to_utc_and_eight_hours(self) -> None:
        user = UserCreate(email=EMAIL, password=PASSWORD)

        assert (user.timezone, user.daily_capacity_minutes) == ("UTC", 480)

    def test_accepts_iana_timezone(self) -> None:
        user = UserCreate(email=EMAIL, password=PASSWORD, timezone="Asia/Kolkata")

        assert user.timezone == "Asia/Kolkata"

    def test_rejects_unknown_timezone(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email=EMAIL, password=PASSWORD, timezone="Mars/Olympus")

    @pytest.mark.parametrize("minutes", [0, 1441])
    def test_rejects_capacity_out_of_range(self, minutes: int) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email=EMAIL, password=PASSWORD, daily_capacity_minutes=minutes)


class TestUserUpdate:
    def test_leaves_unset_fields_out(self) -> None:
        update = UserUpdate(daily_capacity_minutes=60)

        assert update.create_update_dict() == {"daily_capacity_minutes": 60}
