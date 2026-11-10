"""Per-account notification preferences; existing accounts inherit role defaults."""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("alert_preferences", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("users", "alert_preferences")
