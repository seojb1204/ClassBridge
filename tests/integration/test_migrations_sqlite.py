from __future__ import annotations

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

from app.db import Base, make_engine


def test_sqlite_upgrade_matches_models_and_downgrade(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    eng = make_engine(url)
    with eng.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    idx = {i["name"] for i in inspect(eng).get_indexes("bookings")}
    assert "uq_bookings_one_active_per_student" in idx
    command.downgrade(cfg, "base")
    assert set(inspect(eng).get_table_names()) <= {"alembic_version"}
    eng.dispose()


def test_feedback_migration_preserves_legacy_private_suggestions(tmp_path):
    url = f"sqlite:///{tmp_path}/legacy.db"
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "0004")
    eng = make_engine(url)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO suggestions (id, category, content, submitted_on, status) "
                          "VALUES ('legacy', 'other', 'private legacy', '2026-11-01', 'new')"))
    command.upgrade(cfg, "head")
    with eng.connect() as conn:
        row = conn.execute(text("SELECT content, is_public, deleted_on FROM suggestions WHERE id='legacy'")).one()
        assert row == ("private legacy", 0, None)
    eng.dispose()
