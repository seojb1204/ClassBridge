"""Allow inactive historical bookings without inventing consultation outcomes.

Revision ID: 0010
Revises: 0009

Schema only. On application startup the completion worker classifies booked
appointments ending on/before its persisted activation marker as expired and
records booking.expired audit entries. Deploy only after this transition is
approved; existing identifiers, notes, and booking events remain intact.
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _replace_status_check(expression: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("ck_bookings_status", "bookings", type_="check")
        op.create_check_constraint("ck_bookings_status", "bookings", expression)
        return
    # SQLite must rebuild the referenced table. Toggle FK enforcement outside
    # transactions, only on this migration connection; verify and restore it.
    with op.get_context().autocommit_block():
        bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
        bind.exec_driver_sql("BEGIN")
        try:
            with op.batch_alter_table("bookings") as batch:
                batch.drop_constraint("ck_bookings_status", type_="check")
                batch.create_check_constraint("ck_bookings_status", expression)
            if bind.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
                raise RuntimeError("Foreign key validation failed after booking schema upgrade")
            bind.exec_driver_sql("COMMIT")
        except Exception:
            bind.exec_driver_sql("ROLLBACK")
            raise
        finally:
            bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def upgrade() -> None:
    _replace_status_check("status IN ('booked','cancelled','completed','no_show','expired')")


def downgrade() -> None:
    # Never silently relabel unknown historical outcomes or reactivate them.
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM bookings WHERE status = 'expired'")):
        raise RuntimeError("Cannot downgrade while expired bookings exist; retain schema and review outcomes first")
    _replace_status_check("status IN ('booked','cancelled','completed','no_show')")
