"""Durable private professor inbox; no historical backfill."""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("inbox_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("created_on", sa.Date(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("recipient_id", "event_key", name="uq_inbox_recipient_event"))
    op.create_index("ix_inbox_recipient_id", "inbox_notifications", ["recipient_id", "id"])


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM inbox_notifications")).scalar():
        raise RuntimeError("Cannot downgrade: preserve existing inbox notifications")
    op.drop_table("inbox_notifications")
