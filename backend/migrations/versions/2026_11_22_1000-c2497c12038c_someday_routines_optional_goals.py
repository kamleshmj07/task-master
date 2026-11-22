"""Optional task goals, Someday postponements, routines, default goal.

- `task.goal_id` becomes nullable: tasks no longer need a goal.
- `task_postponement.to_date` becomes nullable: NULL means "moved to Someday".
- New `routine` and `routine_completion` tables.
- Every existing user gets the default "Essentials" goal new users receive.

Downgrade deletes goal-less tasks, Someday postponements and all routines,
since the old schema cannot hold them. It keeps the Essentials goals.

Revision ID: c2497c12038c
Revises: e04dfba4791d
Create Date: 2026-11-22 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c2497c12038c"
down_revision: str | None = "e04dfba4791d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOVES_FORWARD = op.f("ck_task_postponement_moves_forward")
# Copied, not imported, so later renames in app code never rewrite history.
DEFAULT_GOAL_TITLE = "Essentials"
DEFAULT_GOAL_WHY = "Everyday responsibilities that keep life running smoothly."


def upgrade() -> None:
    op.alter_column("task", "goal_id", nullable=True)
    op.alter_column("task_postponement", "to_date", nullable=True)
    op.drop_constraint(MOVES_FORWARD, "task_postponement", type_="check")
    op.create_check_constraint(
        MOVES_FORWARD,
        "task_postponement",
        "from_date IS NULL OR to_date IS NULL OR to_date > from_date",
    )
    _create_routine_tables()
    _add_default_goals()


def downgrade() -> None:
    op.drop_table("routine_completion")
    op.drop_table("routine")
    op.execute("DELETE FROM task_postponement WHERE to_date IS NULL")
    op.drop_constraint(MOVES_FORWARD, "task_postponement", type_="check")
    op.create_check_constraint(
        MOVES_FORWARD, "task_postponement", "from_date IS NULL OR to_date > from_date"
    )
    op.alter_column("task_postponement", "to_date", nullable=False)
    op.execute("DELETE FROM task WHERE goal_id IS NULL")
    op.alter_column("task", "goal_id", nullable=False)


def _create_routine_tables() -> None:
    op.create_table(
        "routine",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("estimate_minutes", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.SmallInteger()), nullable=True),
        sa.Column("day_of_month", sa.SmallInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
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
        sa.CheckConstraint(
            "end_date >= start_date", name=op.f("ck_routine_ends_after_start")
        ),
        sa.CheckConstraint(
            "estimate_minutes > 0", name=op.f("ck_routine_estimate_positive")
        ),
        sa.CheckConstraint(
            "(frequency = 'weekly') = (weekdays IS NOT NULL)",
            name=op.f("ck_routine_weekly_has_days"),
        ),
        sa.CheckConstraint(
            "weekdays IS NULL OR (cardinality(weekdays) > 0"
            " AND weekdays <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::smallint[])",
            name=op.f("ck_routine_weekdays_valid"),
        ),
        sa.CheckConstraint(
            "(frequency = 'monthly') = (day_of_month IS NOT NULL)",
            name=op.f("ck_routine_monthly_has_day"),
        ),
        sa.CheckConstraint(
            "day_of_month BETWEEN 1 AND 31", name=op.f("ck_routine_day_of_month_range")
        ),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')",
            name=op.f("ck_routine_routinefrequency"),
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "user_id"],
            ["goal.id", "goal.user_id"],
            name=op.f("fk_routine_goal_id_user_id_goal"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_routine_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_routine")),
        sa.UniqueConstraint("id", "user_id", name=op.f("uq_routine_id_user_id")),
    )
    op.create_index(op.f("ix_routine_goal_id"), "routine", ["goal_id"])
    op.create_index(op.f("ix_routine_user_id"), "routine", ["user_id"])
    op.create_table(
        "routine_completion",
        sa.Column("routine_id", sa.Uuid(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["routine_id"],
            ["routine.id"],
            name=op.f("fk_routine_completion_routine_id_routine"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "routine_id", "completed_on", name=op.f("pk_routine_completion")
        ),
    )


def _add_default_goals() -> None:
    """Give every existing user the default goal, as registration now does."""
    op.execute(
        sa.text(
            "INSERT INTO goal (id, user_id, title, why, status)"
            " SELECT gen_random_uuid(), u.id, :title, :why, 'active'"
            ' FROM "user" u WHERE NOT EXISTS ('
            "  SELECT 1 FROM goal g WHERE g.user_id = u.id AND g.title = :title"
            " )"
        ).bindparams(title=DEFAULT_GOAL_TITLE, why=DEFAULT_GOAL_WHY)
    )
