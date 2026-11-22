"""Add the user's display name, asked for on first sign-in.

Revision ID: c2e193cd6125
Revises: a4af65cba2b1
Create Date: 2026-11-23 11:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c2e193cd6125"
down_revision: str | None = "a4af65cba2b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("display_name", sa.String(length=100)))


def downgrade() -> None:
    op.drop_column("user", "display_name")
