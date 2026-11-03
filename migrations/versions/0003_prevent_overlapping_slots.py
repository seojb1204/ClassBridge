"""Reject overlapping open consultation slots in PostgreSQL.

Revision ID: 0003
Revises: 0002
This migration intentionally fails when historical open slots overlap,
instead of changing or deleting reservations.
"""
from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""
        ALTER TABLE public.slots
        ADD CONSTRAINT ex_slots_no_overlap_open
        EXCLUDE USING gist (tstzrange(start_at, end_at, '[)') WITH &&)
        WHERE (status = 'open')
    """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.slots DROP CONSTRAINT ex_slots_no_overlap_open")
