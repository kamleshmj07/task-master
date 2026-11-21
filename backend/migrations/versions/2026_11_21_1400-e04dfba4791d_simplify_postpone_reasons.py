"""Simplify postpone reasons to stuck/dreading/blocked/other and add a note.

The six original reasons collapse onto the three root causes:
unclear, too_big -> stuck; boring, anxious -> dreading; blocked, no_time ->
blocked. `other` requires a free-text note.

Downgrade is lossy: each new reason maps back to one old reason, `other`
becomes `unclear`, and notes are dropped.

Revision ID: e04dfba4791d
Revises: af280e9918d3
Create Date: 2026-11-21 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e04dfba4791d"
down_revision: str | None = "af280e9918d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "task_postponement"
REASON_CHECK = op.f("ck_task_postponement_postponereason")
NOTE_CHECK = op.f("ck_task_postponement_other_has_note")

OLD_REASONS = ("unclear", "too_big", "boring", "anxious", "blocked", "no_time")
NEW_REASONS = ("stuck", "dreading", "blocked", "other")
UPGRADE_MAP = {
    "unclear": "stuck",
    "too_big": "stuck",
    "boring": "dreading",
    "anxious": "dreading",
    "no_time": "blocked",
}
DOWNGRADE_MAP = {"stuck": "unclear", "dreading": "boring", "other": "unclear"}


def _remap_reasons(mapping: dict[str, str]) -> None:
    reason = sa.table(TABLE, sa.column("reason", sa.String))
    for old, new in mapping.items():
        op.execute(reason.update().where(reason.c.reason == old).values(reason=new))


def _reason_check_sql(values: Sequence[str]) -> str:
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"reason IN ({allowed})"


def upgrade() -> None:
    op.drop_constraint(REASON_CHECK, TABLE, type_="check")
    _remap_reasons(UPGRADE_MAP)
    op.create_check_constraint(REASON_CHECK, TABLE, _reason_check_sql(NEW_REASONS))
    op.add_column(TABLE, sa.Column("note", sa.String(length=280), nullable=True))
    op.create_check_constraint(
        NOTE_CHECK,
        TABLE,
        "reason <> 'other' OR length(trim(coalesce(note, ''))) > 0",
    )


def downgrade() -> None:
    op.drop_constraint(NOTE_CHECK, TABLE, type_="check")
    op.drop_column(TABLE, "note")
    op.drop_constraint(REASON_CHECK, TABLE, type_="check")
    _remap_reasons(DOWNGRADE_MAP)
    op.create_check_constraint(REASON_CHECK, TABLE, _reason_check_sql(OLD_REASONS))
