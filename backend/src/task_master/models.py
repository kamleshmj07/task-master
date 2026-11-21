"""SQLAlchemy ORM models for the MVP domain."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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


class TaskStatus(StrEnum):
    """Lifecycle of a task."""

    TODO = "todo"
    DONE = "done"


class PostponeReason(StrEnum):
    """Why a task was postponed; drives the suggested fix."""

    UNCLEAR = "unclear"
    TOO_BIG = "too_big"
    BORING = "boring"
    ANXIOUS = "anxious"
    BLOCKED = "blocked"
    NO_TIME = "no_time"


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    """Persist enum values (e.g. "too_big"), not member names."""
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
    __table_args__ = (
        CheckConstraint(
            "daily_capacity_minutes BETWEEN 1 AND 1440", name="daily_capacity_range"
        ),
    )

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
    daily_capacity_minutes: Mapped[int] = mapped_column(default=480)


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
    """A unit of work toward a goal, always with a concrete next action."""

    __tablename__ = "task"
    __table_args__ = (
        # Composite FK guarantees a task's owner is its goal's owner.
        ForeignKeyConstraint(
            ["goal_id", "user_id"],
            ["goal.id", "goal.user_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("estimate_minutes > 0", name="estimate_positive"),
        CheckConstraint("postpone_count >= 0", name="postpone_count_non_negative"),
        CheckConstraint("length(trim(next_action)) > 0", name="next_action_present"),
        UniqueConstraint("id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True
    )
    goal_id: Mapped[uuid.UUID] = mapped_column(index=True)
    title: Mapped[str] = mapped_column(String(200))
    next_action: Mapped[str] = mapped_column(String(500))
    estimate_minutes: Mapped[int | None]
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[TaskStatus] = mapped_column(
        _enum_column(TaskStatus), default=TaskStatus.TODO
    )
    postpone_count: Mapped[int] = mapped_column(default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskPostponement(Base):
    """One deferral of a task, kept as history for procrastination diagnosis."""

    __tablename__ = "task_postponement"
    __table_args__ = (
        CheckConstraint(
            "from_date IS NULL OR to_date > from_date", name="moves_forward"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), index=True
    )
    from_date: Mapped[date | None] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[PostponeReason] = mapped_column(_enum_column(PostponeReason))
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
