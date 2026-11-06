"""Optional anonymous survey access; preserve existing login-only surveys."""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("surveys", sa.Column("access_mode", sa.String(20), server_default="login", nullable=False))
    op.add_column("surveys", sa.Column("public_token", sa.String(32), nullable=True))
    op.create_index("ix_surveys_public_token", "surveys", ["public_token"], unique=True)
    op.create_table("survey_guest_participations",
                    sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True),
                    sa.Column("browser_hash", sa.String(64), primary_key=True))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.survey_guest_participations ENABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON public.survey_guest_participations FROM PUBLIC")
        for role in ("anon", "authenticated"):
            if op.get_bind().execute(sa.text("SELECT 1 FROM pg_roles WHERE rolname=:role"), {"role": role}).scalar():
                op.execute(f"REVOKE ALL ON public.survey_guest_participations FROM {role}")


def downgrade():
    # Disposable test DBs only. Operational rollback retains additive schema.
    op.drop_table("survey_guest_participations")
    op.drop_index("ix_surveys_public_token", table_name="surveys")
    op.drop_column("surveys", "public_token")
    op.drop_column("surveys", "access_mode")
