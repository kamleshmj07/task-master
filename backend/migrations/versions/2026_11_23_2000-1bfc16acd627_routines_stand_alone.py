"""Routines stand alone: drop their link to a goal.

Existing routines keep everything else; only the goal link goes. Deleting a
goal no longer deletes routines.

Downgrade restores the column, empty.

Revision ID: 1bfc16acd627
Revises: f817fc7fa51d
Create Date: 2026-11-23 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1bfc16acd627"
down_revision: str | None = "f817fc7fa51d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("fk_routine_goal_id_user_id_goal"), "routine", type_="foreignkey"
    )
    op.drop_index(op.f("ix_routine_goal_id"), table_name="routine")
    op.drop_column("routine", "goal_id")


def downgrade() -> None:
    op.add_column("routine", sa.Column("goal_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_routine_goal_id"), "routine", ["goal_id"])
    op.create_foreign_key(
        op.f("fk_routine_goal_id_user_id_goal"),
        "routine",
        "goal",
        ["goal_id", "user_id"],
        ["id", "user_id"],
        ondelete="CASCADE",
    )
