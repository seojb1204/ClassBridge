"""Private scheduled staff reminders; additive, no historical backfill."""
import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('inbox_notifications', sa.Column('message', sa.String(240), nullable=True))
    op.create_table('staff_reminders',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('recipient_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('message', sa.String(240), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_staff_reminder_due', 'staff_reminders', ['dispatched_at', 'cancelled_at', 'scheduled_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('ALTER TABLE staff_reminders ENABLE ROW LEVEL SECURITY')


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT count(*) FROM staff_reminders')).scalar() or bind.execute(
            sa.text('SELECT count(*) FROM inbox_notifications WHERE message IS NOT NULL')).scalar():
        raise RuntimeError('Cannot downgrade: preserve scheduled reminders')
    op.drop_table('staff_reminders')
    op.drop_column('inbox_notifications', 'message')
