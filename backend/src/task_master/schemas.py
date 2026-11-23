"""Request and response schemas for goals, tasks, routines and plans."""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

from task_master.models import (
    POSTPONE_NOTE_MAX_LENGTH,
    GoalStatus,
    Notification,
    NotificationKind,
    PostponeReason,
    RoutineFrequency,
    TaskStatus,
    TaskStep,
)

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
StepText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
Why = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
TimeLimitMinutes = Annotated[int, Field(ge=1, le=1440)]
MAX_STEPS = 50


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
    """New task: its steps, in order, starting with a concrete first one.

    Leaving out `due_date` puts the task in Someday.
    """

    goal_id: uuid.UUID | None = None
    title: Title
    steps: list[StepText] = Field(min_length=1, max_length=MAX_STEPS)
    time_limit_minutes: TimeLimitMinutes | None = None
    due_date: date | None = None


class TaskUpdate(PatchModel):
    """Partial task update. Setting `status` maintains `completed_at`.

    Steps change through the task's `/steps` routes.
    """

    REQUIRED_IF_SET = frozenset({"title", "status"})

    goal_id: uuid.UUID | None = None
    title: Title | None = None
    time_limit_minutes: TimeLimitMinutes | None = None
    due_date: date | None = None
    status: TaskStatus | None = None


class TaskView(StrEnum):
    """Where a task appears on the Tasks page; each task is in exactly one.

    - review: open, and either every step is done or the due date has passed
    - scheduled: open, dated today or later, with steps left
    - someday: open, undated, with steps left
    - done: completed
    """

    SCHEDULED = "scheduled"
    REVIEW = "review"
    SOMEDAY = "someday"
    DONE = "done"


class TaskCounts(BaseModel):
    """Task totals per view, so clients can page without losing counts."""

    scheduled: int
    review: int
    someday: int
    done: int


class StepOrder(BaseModel):
    """Every step of a task, by id, in the new order."""

    step_ids: list[uuid.UUID] = Field(min_length=1, max_length=MAX_STEPS)


class StepCreate(BaseModel):
    """A step added to the end of a task."""

    text: StepText


class StepUpdate(PatchModel):
    """Rename a step, or tick it off (`done: true`) or back (`done: false`)."""

    REQUIRED_IF_SET = frozenset({"text", "done"})

    text: StepText | None = None
    done: bool | None = None


class StepRead(BaseModel):
    """One step of a task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    text: str
    done: bool

    @model_validator(mode="before")
    @classmethod
    def derive_done(cls, data: Any) -> Any:
        """A stored step is done when it has a `done_at` time."""
        if isinstance(data, TaskStep):
            return {"id": data.id, "text": data.text, "done": data.done_at is not None}
        return data


class TaskRead(BaseModel):
    """A task as returned by the API, with its steps in order.

    `next_step` is the first unfinished step: the task's next action.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID | None
    title: str
    steps: list[StepRead]
    time_limit_minutes: int | None
    due_date: date | None
    status: TaskStatus
    postpone_count: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def next_step(self) -> str | None:
        """Text of the first step not yet done, if any."""
        return next((step.text for step in self.steps if not step.done), None)


PostponeNote = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=POSTPONE_NOTE_MAX_LENGTH)
]


class PostponeRequest(BaseModel):
    """Move a task to a later date, or to Someday with `to_date: null`."""

    to_date: date | None
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
    to_date: date | None
    reason: PostponeReason
    note: str | None
    created_at: datetime


class SuggestionRead(BaseModel):
    """The fix suggested for a postponement."""

    model_config = ConfigDict(from_attributes=True)

    headline: str
    actions: list[str]
    reflection: str | None


class NotificationRead(BaseModel):
    """Something worth a look: a goal update or tasks coming due."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: NotificationKind
    title: str
    body: str
    goal_id: uuid.UUID | None
    created_at: datetime
    read: bool

    @model_validator(mode="before")
    @classmethod
    def derive_read(cls, data: Any) -> Any:
        """A stored notification is read once it has a `read_at` time."""
        if isinstance(data, Notification):
            return {
                **{
                    key: getattr(data, key) for key in cls.model_fields if key != "read"
                },
                "read": data.read_at is not None,
            }
        return data


class UnreadCount(BaseModel):
    """How many notifications are still unread."""

    unread: int


class PostponeResponse(BaseModel):
    """The updated task, what was recorded, and how to stop postponing."""

    task: TaskRead
    postponement: PostponementRead
    suggestion: SuggestionRead


Weekday = Annotated[int, Field(ge=0, le=6)]
DayOfMonth = Annotated[int, Field(ge=1, le=31)]


class RoutineSchedule(BaseModel):
    """When a routine is due. Shared by create and update payloads."""

    frequency: RoutineFrequency
    weekdays: list[Weekday] | None = None
    day_of_month: DayOfMonth | None = None
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def check_schedule(self) -> Self:
        """Each frequency takes exactly the detail it needs."""
        check_schedule(self.frequency, self.weekdays, self.day_of_month)
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.weekdays is not None:
            self.weekdays = sorted(set(self.weekdays))
        return self


def check_schedule(
    frequency: RoutineFrequency, weekdays: list[int] | None, day: int | None
) -> None:
    """Raise `ValueError` unless the schedule fields match `frequency`."""
    weekly = frequency is RoutineFrequency.WEEKLY
    monthly = frequency is RoutineFrequency.MONTHLY
    if weekly != bool(weekdays):
        raise ValueError("weekdays are required for weekly routines, and only them")
    if monthly != (day is not None):
        raise ValueError("day_of_month is required for monthly routines, and only them")


class RoutineCreate(RoutineSchedule):
    """New routine. Weekdays: 0 = Monday ... 6 = Sunday."""

    title: Title
    goal_id: uuid.UUID | None = None


class RoutineUpdate(PatchModel):
    """Partial routine update; schedule fields are checked together."""

    REQUIRED_IF_SET = frozenset({"title", "frequency", "start_date", "end_date"})

    title: Title | None = None
    goal_id: uuid.UUID | None = None
    frequency: RoutineFrequency | None = None
    weekdays: list[Weekday] | None = None
    day_of_month: DayOfMonth | None = None
    start_date: date | None = None
    end_date: date | None = None


class RoutineRead(BaseModel):
    """A routine as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID | None
    title: str
    frequency: RoutineFrequency
    weekdays: list[int] | None
    day_of_month: int | None
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime


class DueRoutine(BaseModel):
    """A routine due on a given day, with whether it was ticked off."""

    routine: RoutineRead
    done: bool
    streak: int


class PlanUpdate(BaseModel):
    """The day's Top 3, most important first."""

    task_ids: list[uuid.UUID] = Field(max_length=3)

    @model_validator(mode="after")
    def reject_duplicates(self) -> Self:
        """A task can hold only one slot."""
        if len(set(self.task_ids)) != len(self.task_ids):
            raise ValueError("A task can appear only once in the Top 3")
        return self


class PlanItem(BaseModel):
    """One ranked Top 3 slot."""

    rank: int
    task: TaskRead


class PlanRead(BaseModel):
    """A day: its Top 3 tasks and, separately, its routines."""

    plan_date: date
    top_three: list[PlanItem]
    routines: list[DueRoutine]
