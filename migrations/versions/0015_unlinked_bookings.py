"""Allow staff reservations without a student account; preserve linked reservations."""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def _nullable(value):
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("bookings", "student_id", existing_type=sa.Integer(), nullable=value)
        return
    # Preserve referenced history/outbox rows during SQLite's required rebuild.
    with op.get_context().autocommit_block():
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
        bind.exec_driver_sql("BEGIN")
        try:
            with op.batch_alter_table("bookings") as batch:
                batch.alter_column("student_id", existing_type=sa.Integer(), nullable=value)
            if bind.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
                raise RuntimeError("Foreign key validation failed after booking schema change")
            bind.exec_driver_sql("COMMIT")
        except Exception:
            bind.exec_driver_sql("ROLLBACK")
            raise
        finally:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade():
    _nullable(True)


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM bookings WHERE student_id IS NULL")):
        raise RuntimeError("계정 미연결 예약이 존재합니다. 데이터를 보존하기 위해 다운그레이드를 중단합니다.")
    _nullable(False)
