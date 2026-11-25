"""Give every goal a soft accent colour.

Existing goals get the colours in palette order, oldest goal first, per
user, so a user's goals start out different from each other.

Revision ID: 5d8e1f3a9b27
Revises: 674ce9fdd30a
Create Date: 2026-11-25 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d8e1f3a9b27"
down_revision: str | None = "674ce9fdd30a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Copied from GoalColor, in palette order.
PALETTE = "'sky', 'periwinkle', 'lilac', 'mauve', 'steel', 'aqua'"
CHECK = op.f("ck_goal_goalcolor")


def upgrade() -> None:
    op.add_column("goal", sa.Column("color", sa.String(length=32), nullable=True))
    op.execute(
        "UPDATE goal SET color = ranked.color FROM ("
        " SELECT id, (ARRAY['sky', 'periwinkle', 'lilac', 'mauve', 'steel', 'aqua'])["
        "  ((row_number() OVER (PARTITION BY user_id ORDER BY created_at, id) - 1)"
        "   % 6) + 1"
        " ] AS color FROM goal"
        ") AS ranked WHERE goal.id = ranked.id"
    )
    op.alter_column("goal", "color", nullable=False)
    op.create_check_constraint(CHECK, "goal", "color IN (" + PALETTE + ")")


def downgrade() -> None:
    op.drop_constraint(CHECK, "goal", type_="check")
    op.drop_column("goal", "color")
