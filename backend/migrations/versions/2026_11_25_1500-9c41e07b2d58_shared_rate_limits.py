"""Keep rate-limit and login-throttle counters in Postgres.

They lived in process memory, which capped the API at one process. In the
database every API process shares them.

Revision ID: 9c41e07b2d58
Revises: 5d8e1f3a9b27
Create Date: 2026-11-25 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9c41e07b2d58"
down_revision: str | None = "5d8e1f3a9b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_window",
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "key", "window_start", name=op.f("pk_rate_limit_window")
        ),
    )
    op.create_index(
        op.f("ix_rate_limit_window_expires_at"), "rate_limit_window", ["expires_at"]
    )
    op.create_table(
        "login_account_failure",
        sa.Column("account_key", sa.String(length=64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("last_failure", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("account_key", name=op.f("pk_login_account_failure")),
    )
    op.create_table(
        "login_ip_failure",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ip_key", sa.String(length=64), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_ip_failure")),
    )
    op.create_index(
        op.f("ix_login_ip_failure_ip_key"),
        "login_ip_failure",
        ["ip_key", "failed_at"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_login_ip_failure_ip_key"), table_name="login_ip_failure")
    op.drop_table("login_ip_failure")
    op.drop_table("login_account_failure")
    op.drop_index(
        op.f("ix_rate_limit_window_expires_at"), table_name="rate_limit_window"
    )
    op.drop_table("rate_limit_window")
