"""Task steps replace next_action; time limits replace estimates; no capacity.

- New `task_step` table. Each task's `next_action` becomes its first step,
  then the column is dropped.
- `task.estimate_minutes` is renamed `time_limit_minutes`: the total time the
  user allows for the task.
- `routine.estimate_minutes` and `user.daily_capacity_minutes` are dropped,
  along with the daily capacity check they fed.

Downgrade restores `next_action` from each task's first step, and resets
capacity to the old 480-minute default; routine estimates are not recovered.

Revision ID: 8a1294aa7071
Revises: c2497c12038c
Create Date: 2026-11-22 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8a1294aa7071"
down_revision: str | None = "c2497c12038c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_steps()
    op.execute(
        "INSERT INTO task_step (id, task_id, position, text)"
        " SELECT gen_random_uuid(), id, 0, next_action FROM task"
    )
    op.drop_constraint(op.f("ck_task_next_action_present"), "task", type_="check")
    op.drop_column("task", "next_action")

    op.drop_constraint(op.f("ck_task_estimate_positive"), "task", type_="check")
    op.alter_column("task", "estimate_minutes", new_column_name="time_limit_minutes")
    op.create_check_constraint(
        op.f("ck_task_time_limit_positive"), "task", "time_limit_minutes > 0"
    )

    op.drop_constraint(op.f("ck_routine_estimate_positive"), "routine", type_="check")
    op.drop_column("routine", "estimate_minutes")

    op.drop_constraint(op.f("ck_user_daily_capacity_range"), "user", type_="check")
    op.drop_column("user", "daily_capacity_minutes")


def downgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "daily_capacity_minutes",
            sa.Integer(),
            server_default="480",
            nullable=False,
        ),
    )
    op.alter_column("user", "daily_capacity_minutes", server_default=None)
    op.create_check_constraint(
        op.f("ck_user_daily_capacity_range"),
        "user",
        "daily_capacity_minutes BETWEEN 1 AND 1440",
    )

    op.add_column("routine", sa.Column("estimate_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_routine_estimate_positive"), "routine", "estimate_minutes > 0"
    )

    op.drop_constraint(op.f("ck_task_time_limit_positive"), "task", type_="check")
    op.alter_column("task", "time_limit_minutes", new_column_name="estimate_minutes")
    op.create_check_constraint(
        op.f("ck_task_estimate_positive"), "task", "estimate_minutes > 0"
    )

    op.add_column("task", sa.Column("next_action", sa.String(length=500)))
    op.execute(
        "UPDATE task SET next_action = COALESCE("
        " (SELECT s.text FROM task_step s WHERE s.task_id = task.id"
        "  ORDER BY s.position, s.id LIMIT 1),"
        " 'Next step')"
    )
    op.alter_column("task", "next_action", nullable=False)
    op.create_check_constraint(
        op.f("ck_task_next_action_present"), "task", "length(trim(next_action)) > 0"
    )
    op.drop_table("task_step")


def _create_steps() -> None:
    op.create_table(
        "task_step",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=500), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(trim(text)) > 0", name=op.f("ck_task_step_text_present")
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_task_step_position_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name=op.f("fk_task_step_task_id_task"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_step")),
    )
    op.create_index(op.f("ix_task_step_task_id"), "task_step", ["task_id"])
