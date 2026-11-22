"""Add notifications: saved postpone tips, shown under the bell until read.

Revision ID: a4af65cba2b1
Revises: 8a1294aa7071
Create Date: 2026-11-23 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4af65cba2b1"
down_revision: str | None = "8a1294aa7071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("task_title", sa.String(length=200), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("headline", sa.String(length=200), nullable=False),
        sa.Column("actions", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("reflection", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "reason IN ('stuck', 'dreading', 'blocked', 'other')",
            name=op.f("ck_notification_postponereason"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["task.id"],
            name=op.f("fk_notification_task_id_task"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_notification_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification")),
    )
    op.create_index(op.f("ix_notification_created_at"), "notification", ["created_at"])
    op.create_index(op.f("ix_notification_task_id"), "notification", ["task_id"])
    op.create_index(op.f("ix_notification_user_id"), "notification", ["user_id"])


def downgrade() -> None:
    op.drop_table("notification")
