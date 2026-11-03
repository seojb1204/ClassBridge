"""Add optional booking detail fields and course labels without deleting old data.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("applicant_name", sa.String(100), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("student_number", sa.String(30), nullable=False, server_default=""))
    op.add_column("bookings", sa.Column("grade", sa.Integer(), nullable=True))
    op.add_column("bookings", sa.Column("consultation_type", sa.String(20), nullable=False,
                                        server_default="other"))
    op.add_column("bookings", sa.Column("consultation_mode", sa.String(20), nullable=False,
                                        server_default="in_person"))
    op.add_column("surveys", sa.Column("course_name", sa.String(120), nullable=False, server_default=""))
    op.add_column("surveys", sa.Column("semester", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    # Destructive: downgrading drops any added metadata. Never run against
    # an operating DB without explicit user approval and a verified backup.
    op.drop_column("surveys", "semester")
    op.drop_column("surveys", "course_name")
    op.drop_column("bookings", "consultation_mode")
    op.drop_column("bookings", "consultation_type")
    op.drop_column("bookings", "grade")
    op.drop_column("bookings", "student_number")
    op.drop_column("bookings", "applicant_name")
