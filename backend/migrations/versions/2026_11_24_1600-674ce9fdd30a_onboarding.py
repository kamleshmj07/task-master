"""Remember when first-run setup was finished.

Accounts that already have tasks are set up already, so they count as
finished and never see the setup card.

Revision ID: 674ce9fdd30a
Revises: 7b06cb22594e
Create Date: 2026-11-24 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "674ce9fdd30a"
down_revision: str | None = "7b06cb22594e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user", sa.Column("onboarded_at", sa.DateTime(timezone=True)))
    op.execute(
        'UPDATE "user" SET onboarded_at = now() '
        'WHERE EXISTS (SELECT 1 FROM task WHERE task.user_id = "user".id)'
    )


def downgrade() -> None:
    op.drop_column("user", "onboarded_at")
