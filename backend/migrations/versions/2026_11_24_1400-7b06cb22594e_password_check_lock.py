"""Count wrong password re-checks and pause them after too many.

Revision ID: 7b06cb22594e
Revises: ca3d3959383b
Create Date: 2026-11-24 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7b06cb22594e"
down_revision: str | None = "ca3d3959383b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "password_check_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "user",
        sa.Column("password_check_locked_until", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("user", "password_check_locked_until")
    op.drop_column("user", "password_check_failures")
