"""Add durable booking email outbox; no backfill or booking changes."""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notification_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_key", sa.String(100), nullable=False, unique=True),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("sender", sa.String(254), nullable=False),
        sa.Column("recipient", sa.String(254), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(50), nullable=False),
        sa.Column("gmail_id", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("subscription_id", sa.Integer()),
        sa.CheckConstraint("status IN ('pending','sending','sent','uncertain','failed','reauth','skipped')",
                           name="ck_notification_status"))
    op.create_index("ix_notification_due", "notification_outbox", ["status", "next_attempt_at"])
    op.create_index("ix_notification_chain", "notification_outbox", ["chain_id", "id"])
    op.create_table("push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("subscription", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sqlite_autoincrement=True)
    op.create_index("ix_push_subscriptions_session_id", "push_subscriptions", ["session_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.notification_outbox ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY")


def downgrade():
    # Disposable databases only. Production rollback leaves pending records intact.
    op.drop_table("notification_outbox")
    op.drop_table("push_subscriptions")
