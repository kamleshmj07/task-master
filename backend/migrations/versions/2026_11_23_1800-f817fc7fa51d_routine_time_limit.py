"""Give routines an optional time limit, like tasks.

Revision ID: f817fc7fa51d
Revises: 30bcd4c2b5e5
Create Date: 2026-11-23 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f817fc7fa51d"
down_revision: str | None = "30bcd4c2b5e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("routine", sa.Column("time_limit_minutes", sa.Integer()))
    op.create_check_constraint(
        op.f("ck_routine_time_limit_positive"), "routine", "time_limit_minutes > 0"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_routine_time_limit_positive"), "routine", type_="check")
    op.drop_column("routine", "time_limit_minutes")
