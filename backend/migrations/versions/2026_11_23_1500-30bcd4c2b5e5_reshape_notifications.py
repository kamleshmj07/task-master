"""Reshape notifications from saved tips into general alerts.

Postpone tips are no longer stored, so the old rows (all tips) are deleted.
A notification now has a `kind`, a `title` and `body`, an optional goal, and
a per-user `key` that stops the same event being notified twice.

Downgrade restores the tip-shaped table, empty.

Revision ID: 30bcd4c2b5e5
Revises: c2e193cd6125
Create Date: 2026-11-23 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "30bcd4c2b5e5"
down_revision: str | None = "c2e193cd6125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "notification"
KINDS = ("goal_deadline", "goal_done", "goal_stale", "tasks_due_soon")


def upgrade() -> None:
    op.execute("DELETE FROM notification")
    op.drop_constraint(op.f("ck_notification_postponereason"), TABLE, type_="check")
    op.drop_index(op.f("ix_notification_task_id"), table_name=TABLE)
    op.drop_constraint(op.f("fk_notification_task_id_task"), TABLE, type_="foreignkey")
    for column in (
        "task_id",
        "task_title",
        "reason",
        "headline",
        "actions",
        "reflection",
    ):
        op.drop_column(TABLE, column)

    op.add_column(TABLE, sa.Column("kind", sa.String(length=32), nullable=False))
    op.add_column(TABLE, sa.Column("key", sa.String(length=200), nullable=False))
    op.add_column(TABLE, sa.Column("title", sa.String(length=300), nullable=False))
    op.add_column(TABLE, sa.Column("body", sa.Text(), nullable=False))
    op.add_column(TABLE, sa.Column("goal_id", sa.Uuid(), nullable=True))
    allowed = ", ".join(f"'{kind}'" for kind in KINDS)
    op.create_check_constraint(
        op.f("ck_notification_notificationkind"), TABLE, f"kind IN ({allowed})"
    )
    op.create_foreign_key(
        op.f("fk_notification_goal_id_goal"),
        TABLE,
        "goal",
        ["goal_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_notification_goal_id"), TABLE, ["goal_id"])
    op.create_unique_constraint(
        op.f("uq_notification_user_id_key"), TABLE, ["user_id", "key"]
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification")
    op.drop_constraint(op.f("uq_notification_user_id_key"), TABLE, type_="unique")
    op.drop_index(op.f("ix_notification_goal_id"), table_name=TABLE)
    op.drop_constraint(op.f("fk_notification_goal_id_goal"), TABLE, type_="foreignkey")
    op.drop_constraint(op.f("ck_notification_notificationkind"), TABLE, type_="check")
    for column in ("kind", "key", "title", "body", "goal_id"):
        op.drop_column(TABLE, column)

    op.add_column(TABLE, sa.Column("task_id", sa.Uuid(), nullable=True))
    op.add_column(TABLE, sa.Column("task_title", sa.String(length=200), nullable=False))
    op.add_column(TABLE, sa.Column("reason", sa.String(length=32), nullable=False))
    op.add_column(TABLE, sa.Column("headline", sa.String(length=200), nullable=False))
    op.add_column(
        TABLE, sa.Column("actions", postgresql.ARRAY(sa.Text()), nullable=False)
    )
    op.add_column(TABLE, sa.Column("reflection", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_notification_postponereason"),
        TABLE,
        "reason IN ('stuck', 'dreading', 'blocked', 'other')",
    )
    op.create_foreign_key(
        op.f("fk_notification_task_id_task"),
        TABLE,
        "task",
        ["task_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_notification_task_id"), TABLE, ["task_id"])
