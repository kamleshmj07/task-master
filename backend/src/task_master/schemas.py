"""Request and response schemas for goals, tasks and postponements."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from task_master.models import (
    POSTPONE_NOTE_MAX_LENGTH,
    GoalStatus,
    PostponeReason,
    TaskStatus,
)

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
NextAction = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Why = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
EstimateMinutes = Annotated[int, Field(ge=1, le=1440)]


class PatchModel(BaseModel):
    """Partial update: omitted fields stay as they are.

    Fields listed in `REQUIRED_IF_SET` may be omitted but not set to null.
    """

    REQUIRED_IF_SET: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def reject_null_for_required(self) -> Self:
        """Refuse `null` for fields the database requires."""
        nulled = {
            name
            for name in self.model_fields_set & self.REQUIRED_IF_SET
            if getattr(self, name) is None
        }
        if nulled:
            raise ValueError(f"Cannot be null: {', '.join(sorted(nulled))}")
        return self

    def changes(self) -> dict[str, Any]:
        """Return only the fields the client sent."""
        return self.model_dump(exclude_unset=True)


class GoalCreate(BaseModel):
    """New goal."""

    title: Title
    why: Why | None = None
    deadline: date | None = None


class GoalUpdate(PatchModel):
    """Partial goal update."""

    REQUIRED_IF_SET = frozenset({"title", "status"})

    title: Title | None = None
    why: Why | None = None
    deadline: date | None = None
    status: GoalStatus | None = None


class GoalRead(BaseModel):
    """A goal as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    why: str | None
    deadline: date | None
    status: GoalStatus
    created_at: datetime
    updated_at: datetime


class TaskCreate(BaseModel):
    """New task; every task needs a goal and a concrete next action."""

    goal_id: uuid.UUID
    title: Title
    next_action: NextAction
    estimate_minutes: EstimateMinutes | None = None
    due_date: date | None = None


class TaskUpdate(PatchModel):
    """Partial task update. Setting `status` maintains `completed_at`."""

    REQUIRED_IF_SET = frozenset({"goal_id", "title", "next_action", "status"})

    goal_id: uuid.UUID | None = None
    title: Title | None = None
    next_action: NextAction | None = None
    estimate_minutes: EstimateMinutes | None = None
    due_date: date | None = None
    status: TaskStatus | None = None


class TaskRead(BaseModel):
    """A task as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    next_action: str
    estimate_minutes: int | None
    due_date: date | None
    status: TaskStatus
    postpone_count: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


PostponeNote = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=POSTPONE_NOTE_MAX_LENGTH)
]


class PostponeRequest(BaseModel):
    """Move a task to a later date, saying why."""

    to_date: date
    reason: PostponeReason
    note: PostponeNote | None = None

    @model_validator(mode="after")
    def require_note_for_other(self) -> Self:
        """Blank notes count as none; `other` must explain itself."""
        if self.note == "":
            self.note = None
        if self.reason is PostponeReason.OTHER and self.note is None:
            raise ValueError("A note is required when the reason is 'other'")
        return self


class PostponementRead(BaseModel):
    """One recorded postponement."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    from_date: date | None
    to_date: date
    reason: PostponeReason
    note: str | None
    created_at: datetime


class SuggestionRead(BaseModel):
    """The fix suggested for a postponement."""

    model_config = ConfigDict(from_attributes=True)

    headline: str
    actions: list[str]
    reflection: str | None


class PostponeResponse(BaseModel):
    """The updated task, what was recorded, and how to stop postponing."""

    task: TaskRead
    postponement: PostponementRead
    suggestion: SuggestionRead
