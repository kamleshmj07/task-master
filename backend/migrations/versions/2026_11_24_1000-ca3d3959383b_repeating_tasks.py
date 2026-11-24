"""Repeating tasks: a repeat rule on each run, and a series id linking runs.

Revision ID: ca3d3959383b
Revises: 1bfc16acd627
Create Date: 2026-11-24 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ca3d3959383b"
down_revision: str | None = "1bfc16acd627"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copied from the model at the time of writing; do not import app code.
FREQUENCIES = ("daily", "weekly", "monthly")
CHECKS = {
    "repeat_has_date_and_series": (
        "repeat_frequency IS NULL OR (due_date IS NOT NULL AND series_id IS NOT NULL)"
    ),
    "repeat_weekly_has_days": (
        "(repeat_frequency IS NOT DISTINCT FROM 'weekly')"
        " = (repeat_weekdays IS NOT NULL)"
    ),
    "repeat_weekdays_valid": (
        "repeat_weekdays IS NULL OR (cardinality(repeat_weekdays) > 0"
        " AND repeat_weekdays <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::smallint[])"
    ),
    "repeat_monthly_has_day": (
        "(repeat_frequency IS NOT DISTINCT FROM 'monthly')"
        " = (repeat_day_of_month IS NOT NULL)"
    ),
    "repeat_day_of_month_range": "repeat_day_of_month BETWEEN 1 AND 31",
    "repeat_until_needs_repeat": (
        "repeat_until IS NULL OR repeat_frequency IS NOT NULL"
    ),
}


def upgrade() -> None:
    op.add_column(
        "task",
        sa.Column(
            "repeat_frequency",
            sa.Enum(
                *FREQUENCIES,
                name="routinefrequency",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
        ),
    )
    op.add_column(
        "task", sa.Column("repeat_weekdays", postgresql.ARRAY(sa.SmallInteger()))
    )
    op.add_column("task", sa.Column("repeat_day_of_month", sa.SmallInteger()))
    op.add_column("task", sa.Column("repeat_until", sa.Date()))
    op.add_column("task", sa.Column("series_id", sa.Uuid()))
    op.create_index(op.f("ix_task_series_id"), "task", ["series_id"])
    for name, condition in CHECKS.items():
        op.create_check_constraint(op.f(f"ck_task_{name}"), "task", condition)


def downgrade() -> None:
    for name in CHECKS:
        op.drop_constraint(op.f(f"ck_task_{name}"), "task", type_="check")
    op.drop_index(op.f("ix_task_series_id"), table_name="task")
    for column in (
        "series_id",
        "repeat_until",
        "repeat_day_of_month",
        "repeat_weekdays",
        "repeat_frequency",
    ):
        op.drop_column("task", column)
