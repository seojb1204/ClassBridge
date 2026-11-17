"""Add student acknowledgement and anonymous receipt hashes; preserve existing records."""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("bookings", sa.Column("student_seen_event_id", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("suggestions", sa.Column("receipt_hash", sa.String(64), nullable=True))
    op.create_index("ix_suggestions_receipt_hash", "suggestions", ["receipt_hash"], unique=True)

def downgrade():
    op.drop_index("ix_suggestions_receipt_hash", table_name="suggestions")
    op.drop_column("suggestions", "receipt_hash")
    op.drop_column("bookings", "student_seen_event_id")
