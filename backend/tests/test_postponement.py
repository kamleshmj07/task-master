"""Tests for postpone suggestions, local dates and the postpone request."""

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from task_master.dependencies import local_today
from task_master.models import PostponeReason
from task_master.postponement import SUGGESTIONS, suggest
from task_master.schemas import PostponeRequest

FUTURE = date(2099, 1, 1)


class TestSuggest:
    @pytest.mark.parametrize("reason", list(PostponeReason))
    def test_every_reason_has_a_fix(self, reason: PostponeReason) -> None:
        suggestion = suggest(reason, blocked_count=0)

        assert suggestion.headline and suggestion.actions

    def test_reasons_get_different_fixes(self) -> None:
        headlines = {suggestion.headline for suggestion in SUGGESTIONS.values()}

        assert len(headlines) == len(PostponeReason)

    def test_stuck_suggests_a_smaller_step(self) -> None:
        assert suggest(PostponeReason.STUCK, 0).headline == (
            "Make the first step smaller"
        )

    def test_blocked_has_no_reflection_at_first(self) -> None:
        assert suggest(PostponeReason.BLOCKED, 2).reflection is None

    def test_third_blocked_asks_about_dread(self) -> None:
        reflection = suggest(PostponeReason.BLOCKED, 3).reflection

        assert reflection is not None and "3 times" in reflection

    def test_only_blocked_gets_the_reflection(self) -> None:
        assert suggest(PostponeReason.DREADING, 5).reflection is None


class TestLocalToday:
    def test_uses_the_users_timezone(self) -> None:
        late_utc = datetime(2026, 11, 21, 20, 0, tzinfo=UTC)

        assert local_today("Asia/Kolkata", late_utc) == date(2026, 11, 22)

    def test_utc_is_unchanged(self) -> None:
        now = datetime(2026, 11, 21, 20, 0, tzinfo=UTC)

        assert local_today("UTC", now) == date(2026, 11, 21)


class TestPostponeRequest:
    def test_other_requires_a_note(self) -> None:
        with pytest.raises(ValidationError):
            PostponeRequest(to_date=FUTURE, reason=PostponeReason.OTHER)

    def test_other_rejects_a_blank_note(self) -> None:
        with pytest.raises(ValidationError):
            PostponeRequest(to_date=FUTURE, reason=PostponeReason.OTHER, note="  ")

    def test_strips_the_note(self) -> None:
        request = PostponeRequest(
            to_date=FUTURE, reason=PostponeReason.OTHER, note="  Sick day "
        )

        assert request.note == "Sick day"

    def test_blank_note_becomes_none_for_other_reasons(self) -> None:
        request = PostponeRequest(to_date=FUTURE, reason=PostponeReason.STUCK, note=" ")

        assert request.note is None

    def test_rejects_note_over_280_chars(self) -> None:
        with pytest.raises(ValidationError):
            PostponeRequest(to_date=FUTURE, reason=PostponeReason.STUCK, note="x" * 281)

    def test_rejects_retired_reason(self) -> None:
        with pytest.raises(ValidationError):
            PostponeRequest.model_validate(
                {"to_date": "2099-01-01", "reason": "too_big"}
            )
