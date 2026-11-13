"""Add staff lecture calendar, never mutate existing consultations."""
import sqlalchemy as sa
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('lectures',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(120), nullable=False),
        sa.Column('location', sa.String(200), nullable=False),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('series_id', sa.String(36), nullable=False),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('end_at > start_at', name='ck_lectures_time_order'),
        sa.CheckConstraint("status IN ('active','cancelled')", name='ck_lectures_status'))
    op.create_index('ix_lectures_start_at', 'lectures', ['start_at'])
    op.create_index('ix_lectures_series_id', 'lectures', ['series_id'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE lectures ENABLE ROW LEVEL SECURITY')


def downgrade():
    if op.get_bind().execute(sa.text('SELECT count(*) FROM lectures')).scalar():
        raise RuntimeError('Cannot downgrade: preserve lecture data')
    op.drop_table('lectures')
