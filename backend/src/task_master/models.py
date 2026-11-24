"""SQLAlchemy ORM models for the MVP domain."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class GoalStatus(StrEnum):
    """Lifecycle of a goal."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class RoutineFrequency(StrEnum):
    """How often a routine repeats."""

    DAILY = "daily"
    WEEKLY = "weekly"  # on the chosen `weekdays`
    MONTHLY = "monthly"  # on `day_of_month`, or the month's last day if shorter


class TaskStatus(StrEnum):
    """Lifecycle of a task."""

    TODO = "todo"
    DONE = "done"


class PostponeReason(StrEnum):
    """Root cause of a postponement; each one calls for a different fix."""

    STUCK = "stuck"  # "I don't know where to start"
    DREADING = "dreading"  # "I don't want to do it"
    BLOCKED = "blocked"  # "Something's in the way"
    OTHER = "other"  # Free text in `note`


POSTPONE_NOTE_MAX_LENGTH = 280


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Persist enum values (e.g. "stuck"), not member names."""
    return [member.value for member in enum_cls]


def _enum_column(enum_cls: type[StrEnum]) -> Enum:
    """Store enums as checked VARCHAR, so adding values needs no type migration."""
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=_enum_values,
        validate_strings=True,
    )


class Base(DeclarativeBase):
    """Declarative base with predictable constraint names for migrations."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Created/updated timestamps maintained by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    """An account. Auth columns match fastapi-users' expected schema."""

    __tablename__ = "user"
    if TYPE_CHECKING:
        # Plain types so `User` satisfies fastapi-users' `UserProtocol`.
        id: uuid.UUID
        email: str
        hashed_password: str
        is_active: bool
        is_superuser: bool
        is_verified: bool
    else:
        id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
        email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
        hashed_password: Mapped[str] = mapped_column(String(1024))
        is_active: Mapped[bool] = mapped_column(default=True)
        is_superuser: Mapped[bool] = mapped_column(default=False)
        is_verified: Mapped[bool] = mapped_column(default=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    # Asked for on first sign-in; NULL until the user has told us.
    display_name: Mapped[str | None] = mapped_column(String(100))
    # When first-run setup was finished; NULL while it still shows.
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Wrong passwords given to re-check it (changing email or password,
    # deleting the account), and how long such checks are refused once too
    # many were wrong. Login has its own throttle (`auth/lockout.py`).
    password_check_failures: Mapped[int] = mapped_column(default=0, server_default="0")
    password_check_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


def utc_now() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(UTC)


class AccessToken(Base):
    """Short-lived opaque bearer token; deleting the row revokes it."""

    __tablename__ = "access_token"

    token: Mapped[str] = mapped_column(String(43), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class RefreshToken(Base):
    """Single-use refresh token. Only its SHA-256 hash is stored.

    Rotation keeps a `family_id`, so reuse of a spent token revokes the family.
    """

    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Goal(TimestampMixin, Base):
    """An outcome the user is working toward; every task belongs to one."""

    __tablename__ = "goal"
    # (id, user_id) is unique so tasks can reference it and inherit the owner.
    __table_args__ = (UniqueConstraint("id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    why: Mapped[str | None] = mapped_column(Text)
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[GoalStatus] = mapped_column(
        _enum_column(GoalStatus), default=GoalStatus.ACTIVE
    )


class Task(TimestampMixin, Base):
    """A unit of work, broken into steps, optionally toward a goal.

    The first unfinished step is the task's next action. A task with no due
    date sits in the Someday bucket.
    """

    __tablename__ = "task"
    __table_args__ = (
        # Composite FK guarantees a task's owner is its goal's owner. It is
        # not checked when `goal_id` is NULL, so goal-less tasks are allowed.
        ForeignKeyConstraint(
            ["goal_id", "user_id"],
            ["goal.id", "goal.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("time_limit_minutes > 0", name="time_limit_positive"),
        CheckConstraint("postpone_count >= 0", name="postpone_count_non_negative"),
        UniqueConstraint("id", "user_id"),
        # A repeating task's run is always dated, and carries exactly the
        # schedule detail its frequency needs (like a routine).
        CheckConstraint(
            "repeat_frequency IS NULL OR (due_date IS NOT NULL"
            " AND series_id IS NOT NULL)",
            name="repeat_has_date_and_series",
        ),
        CheckConstraint(
            "(repeat_frequency IS NOT DISTINCT FROM 'weekly')"
            " = (repeat_weekdays IS NOT NULL)",
            name="repeat_weekly_has_days",
        ),
        CheckConstraint(
            "repeat_weekdays IS NULL OR (cardinality(repeat_weekdays) > 0"
            " AND repeat_weekdays <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::smallint[])",
            name="repeat_weekdays_valid",
        ),
        CheckConstraint(
            "(repeat_frequency IS NOT DISTINCT FROM 'monthly')"
            " = (repeat_day_of_month IS NOT NULL)",
            name="repeat_monthly_has_day",
        ),
        CheckConstraint(
            "repeat_day_of_month BETWEEN 1 AND 31", name="repeat_day_of_month_range"
        ),
        CheckConstraint(
            "repeat_until IS NULL OR repeat_frequency IS NOT NULL",
            name="repeat_until_needs_repeat",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Total time the user allows for the task, across all sittings.
    time_limit_minutes: Mapped[int | None]
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[TaskStatus] = mapped_column(
        _enum_column(TaskStatus), default=TaskStatus.TODO
    )
    postpone_count: Mapped[int] = mapped_column(default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Repeating tasks (`repeats.py`): each run is a task; finishing one adds
    # the next. Runs of one series share `series_id`.
    repeat_frequency: Mapped[RoutineFrequency | None] = mapped_column(
        _enum_column(RoutineFrequency)
    )
    repeat_weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    repeat_day_of_month: Mapped[int | None] = mapped_column(SmallInteger)
    repeat_until: Mapped[date | None] = mapped_column(Date)
    series_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    steps: Mapped[list[TaskStep]] = relationship(
        order_by="TaskStep.position, TaskStep.id",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    # Read-only: postponements are written through their own table and go
    # with the task through the database's ON DELETE CASCADE.
    postponements: Mapped[list[TaskPostponement]] = relationship(
        lazy="selectin", viewonly=True
    )

    @property
    def repeat(self) -> dict[str, object] | None:
        """The repeat rule, or None for a one-off task."""
        if self.repeat_frequency is None:
            return None
        return {
            "frequency": self.repeat_frequency,
            "weekdays": self.repeat_weekdays,
            "day_of_month": self.repeat_day_of_month,
            "until": self.repeat_until,
        }

    @property
    def postponement_reasons(self) -> dict[PostponeReason, int]:
        """How many times the task was postponed for each reason."""
        counts: dict[PostponeReason, int] = {}
        for postponement in self.postponements:
            counts[postponement.reason] = counts.get(postponement.reason, 0) + 1
        return counts


class TaskStep(Base):
    """One checklist step of a task, in `position` order."""

    __tablename__ = "task_step"
    __table_args__ = (
        CheckConstraint("length(trim(text)) > 0", name="text_present"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    text: Mapped[str] = mapped_column(String(500))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskPostponement(Base):
    """One deferral of a task, kept as history for procrastination diagnosis."""

    __tablename__ = "task_postponement"
    __table_args__ = (
        CheckConstraint(
            "from_date IS NULL OR to_date IS NULL OR to_date > from_date",
            name="moves_forward",
        ),
        CheckConstraint(
            "reason <> 'other' OR length(trim(coalesce(note, ''))) > 0",
            name="other_has_note",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), index=True
    )
    from_date: Mapped[date | None] = mapped_column(Date)
    # NULL means the task was moved to Someday.
    to_date: Mapped[date | None] = mapped_column(Date)
    reason: Mapped[PostponeReason] = mapped_column(_enum_column(PostponeReason))
    note: Mapped[str | None] = mapped_column(String(POSTPONE_NOTE_MAX_LENGTH))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DailyPlan(TimestampMixin, Base):
    """A user's plan for one calendar day."""

    __tablename__ = "daily_plan"
    __table_args__ = (
        UniqueConstraint("user_id", "plan_date"),
        UniqueConstraint("id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE")
    )
    plan_date: Mapped[date] = mapped_column(Date)


class DailyPlanItem(Base):
    """A ranked Top 3 slot in a daily plan."""

    __tablename__ = "daily_plan_item"
    __table_args__ = (
        # Composite FKs guarantee the plan and the task share one owner.
        ForeignKeyConstraint(
            ["plan_id", "user_id"],
            ["daily_plan.id", "daily_plan.user_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["task.id", "task.user_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("plan_id", "rank"),
        CheckConstraint("rank BETWEEN 1 AND 3", name="rank_top_three"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[uuid.UUID]
    rank: Mapped[int] = mapped_column(SmallInteger)


class Routine(TimestampMixin, Base):
    """A recurring chore, ticked off on each day it is due.

    Routines stand alone: no goal, no steps. Unlike tasks they are never
    postponed and never enter the Top 3; a missed day simply stays unticked.
    """

    __tablename__ = "routine"
    __table_args__ = (
        UniqueConstraint("id", "user_id"),
        CheckConstraint("end_date >= start_date", name="ends_after_start"),
        CheckConstraint("time_limit_minutes > 0", name="time_limit_positive"),
        CheckConstraint(
            "(frequency = 'weekly') = (weekdays IS NOT NULL)", name="weekly_has_days"
        ),
        CheckConstraint(
            "weekdays IS NULL OR (cardinality(weekdays) > 0"
            " AND weekdays <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::smallint[])",
            name="weekdays_valid",
        ),
        CheckConstraint(
            "(frequency = 'monthly') = (day_of_month IS NOT NULL)",
            name="monthly_has_day",
        ),
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="day_of_month_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    # Most time to spend each time it is due, like a task's time limit.
    time_limit_minutes: Mapped[int | None]
    frequency: Mapped[RoutineFrequency] = mapped_column(_enum_column(RoutineFrequency))
    # ISO weekday numbers minus one: 0 = Monday ... 6 = Sunday.
    weekdays: Mapped[list[int] | None] = mapped_column(ARRAY(SmallInteger))
    day_of_month: Mapped[int | None] = mapped_column(SmallInteger)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)


class RoutineCompletion(Base):
    """A routine ticked off on one day."""

    __tablename__ = "routine_completion"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("routine.id", ondelete="CASCADE"), primary_key=True
    )
    completed_on: Mapped[date] = mapped_column(Date, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NotificationKind(StrEnum):
    """Why a notification was created."""

    GOAL_DEADLINE = "goal_deadline"  # an active goal's deadline is near
    GOAL_DONE = "goal_done"  # every task under an active goal is finished
    GOAL_STALE = "goal_stale"  # an active goal has not moved for a while
    TASKS_DUE_SOON = "tasks_due_soon"  # one daily summary of tasks due soon


class Notification(Base):
    """Something worth a look, shown under the bell until read.

    `key` identifies the event (e.g. one goal's deadline, or one day's
    summary), so checking again never creates a duplicate.
    """

    __tablename__ = "notification"
    __table_args__ = (UniqueConstraint("user_id", "key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[NotificationKind] = mapped_column(_enum_column(NotificationKind))
    key: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    # The goal it is about; kept (unlinked) if the goal is later deleted.
    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("goal.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
