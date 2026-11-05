"""Add reversible trash and opt-in public suggestions; preserve all existing data."""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("suggestions", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("suggestions", sa.Column("deleted_on", sa.Date(), nullable=True))
    op.add_column("surveys", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table("suggestion_replies",
                    sa.Column("id", sa.String(36), primary_key=True),
                    sa.Column("suggestion_id", sa.String(36), sa.ForeignKey("suggestions.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("content", sa.Text(), nullable=False),
                    sa.Column("created_on", sa.Date(), nullable=False))
    op.create_index("ix_suggestion_replies_suggestion_id", "suggestion_replies", ["suggestion_id"])
    # Keep the database-wide protection established by 0002 for every new table.
    # App connections use the owner role; API roles receive no policies or grants.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.suggestion_replies ENABLE ROW LEVEL SECURITY")


def downgrade():
    # Destructive: only use on disposable tests or after explicit data-loss approval.
    # Operational rollback should keep this additive schema and roll back code.
    op.drop_table("suggestion_replies")
    op.drop_column("surveys", "deleted_at")
    op.drop_column("suggestions", "deleted_on")
    op.drop_column("suggestions", "is_public")
