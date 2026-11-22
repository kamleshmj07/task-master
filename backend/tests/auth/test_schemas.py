"""Tests for account schema validation."""

import pytest
from pydantic import ValidationError

from task_master.auth.schemas import UserCreate, UserUpdate

EMAIL = "ada@example.com"
PASSWORD = "correct-horse-battery"


class TestUserCreate:
    def test_defaults_to_utc(self) -> None:
        user = UserCreate(email=EMAIL, password=PASSWORD)

        assert user.timezone == "UTC"

    def test_accepts_iana_timezone(self) -> None:
        user = UserCreate(email=EMAIL, password=PASSWORD, timezone="Asia/Kolkata")

        assert user.timezone == "Asia/Kolkata"

    def test_rejects_unknown_timezone(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(email=EMAIL, password=PASSWORD, timezone="Mars/Olympus")


class TestUserUpdate:
    def test_leaves_unset_fields_out(self) -> None:
        update = UserUpdate(timezone="Asia/Kolkata")

        assert update.create_update_dict() == {"timezone": "Asia/Kolkata"}
