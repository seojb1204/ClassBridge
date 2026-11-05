"""Add private developer requests without changing anonymous feedback."""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("support_tickets",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
                    sa.Column("title", sa.String(120), nullable=False),
                    sa.Column("category", sa.String(20), nullable=False),
                    sa.Column("page_path", sa.String(200), nullable=False),
                    sa.Column("status", sa.String(20), nullable=False),
                    sa.Column("developer_unread", sa.Boolean(), nullable=False),
                    sa.Column("owner_unread", sa.Boolean(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
                    sa.CheckConstraint("category IN ('bug','feature','help')", name="ck_support_category"),
                    sa.CheckConstraint("status IN ('received','reviewing','completed')", name="ck_support_status"))
    op.create_index("ix_support_tickets_owner_id", "support_tickets", ["owner_id"])
    op.create_table("support_messages",
                    sa.Column("id", sa.Integer(), primary_key=True),
                    sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
                              nullable=False),
                    sa.Column("is_developer", sa.Boolean(), nullable=False),
                    sa.Column("content", sa.Text(), nullable=False),
                    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.support_tickets ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE public.support_messages ENABLE ROW LEVEL SECURITY")


def downgrade():
    # Destructive: disposable test databases only; operational rollback keeps this schema.
    op.drop_table("support_messages")
    op.drop_table("support_tickets")
