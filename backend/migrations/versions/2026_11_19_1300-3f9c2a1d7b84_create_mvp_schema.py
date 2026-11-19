"""Create MVP schema: users, goals, tasks, postponements, daily plans.

Revision ID: 3f9c2a1d7b84
Revises:
Create Date: 2026-11-19 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3f9c2a1d7b84"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def _enum_check(column: str, name: str, values: Sequence[str]) -> sa.CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({allowed})", name=op.f(name))


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=1024), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("daily_capacity_minutes", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "daily_capacity_minutes BETWEEN 1 AND 1440",
            name=op.f("ck_user_daily_capacity_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "goal",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("why", sa.Text(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        *_timestamps(),
        _enum_check(
            "status", "ck_goal_goalstatus", ("active", "completed", "archived")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_goal_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goal")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_goal_id_user_id")),
    )
    op.create_index(op.f("ix_goal_user_id"), "goal", ["user_id"])

    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("next_action", sa.String(length=500), nullable=False),
        sa.Column("estimate_minutes", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("postpone_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "estimate_minutes > 0", name=op.f("ck_task_estimate_positive")
        ),
        sa.CheckConstraint(
            "postpone_count >= 0", name=op.f("ck_task_postpone_count_non_negative")
        ),
        sa.CheckConstraint(
            "length(trim(next_action)) > 0", name=op.f("ck_task_next_action_present")
        ),
        _enum_check("status", "ck_task_taskstatus", ("todo", "done")),
        sa.ForeignKeyConstraint(
            ["goal_id", "user_id"],
            ["goal.id", "goal.user_id"],
            name=op.f("fk_task_goal_id_user_id_goal"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_task_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_task_id_user_id")),
    )
    op.create_index(op.f("ix_task_goal_id"), "task", ["goal_id"])
    op.create_index(op.f("ix_task_user_id"), "task", ["user_id"])

    op.create_table(
        "task_postponement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=True),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_date IS NULL OR to_date > from_date",
            name=op.f("ck_task_postponement_moves_forward"),
        ),
        _enum_check(
            "reason",
            "ck_task_postponement_postponereason",
            ("unclear", "too_big", "boring", "anxious", "blocked", "no_time"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name=op.f("fk_task_postponement_task_id_task"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_postponement")),
    )
    op.create_index(
        op.f("ix_task_postponement_task_id"), "task_postponement", ["task_id"]
    )

    op.create_table(
        "daily_plan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_daily_plan_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_plan")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_daily_plan_id_user_id")),
        sa.UniqueConstraint(
            "user_id", "plan_date", name=op.f("uq_daily_plan_user_id_plan_date")
        ),
    )

    op.create_table(
        "daily_plan_item",
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "rank BETWEEN 1 AND 3", name=op.f("ck_daily_plan_item_rank_top_three")
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "user_id"],
            ["daily_plan.id", "daily_plan.user_id"],
            name=op.f("fk_daily_plan_item_plan_id_user_id_daily_plan"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id", "user_id"],
            ["task.id", "task.user_id"],
            name=op.f("fk_daily_plan_item_task_id_user_id_task"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("plan_id", "task_id", name=op.f("pk_daily_plan_item")),
        sa.UniqueConstraint(
            "plan_id", "rank", name=op.f("uq_daily_plan_item_plan_id_rank")
        ),
    )
    op.create_index(op.f("ix_daily_plan_item_task_id"), "daily_plan_item", ["task_id"])


def downgrade() -> None:
    op.drop_table("daily_plan_item")
    op.drop_table("daily_plan")
    op.drop_table("task_postponement")
    op.drop_table("task")
    op.drop_table("goal")
    op.drop_table("user")
