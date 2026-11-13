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


def test_survey_access_migration_keeps_existing_survey_login_only(tmp_path):
    url = f"sqlite:///{tmp_path}/old-survey.db"
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "0006")
    eng = make_engine(url)
    with eng.begin() as conn:
        conn.execute(text("INSERT INTO users (id,google_sub,email,name,role,is_active,created_at) "
                          "VALUES (1,'legacy','admin@example.test','legacy','admin',1,'2026-11-01')"))
        conn.execute(text("INSERT INTO surveys (id,title,description,status,min_results,created_by_id,"
                          "created_at,updated_at,course_name,semester) VALUES "
                          "(1,'legacy','existing','published',5,:actor,'2026-11-01','2026-11-01','','')"),
                     {"actor": 1})
    command.upgrade(cfg, "head")
    with eng.connect() as conn:
        assert conn.execute(text("SELECT title,access_mode,public_token FROM surveys WHERE id=1")).one() == (
            "legacy", "login", None)
    eng.dispose()


def test_expired_migration_preserves_referenced_booking(tmp_path):
    from datetime import timedelta

    from sqlalchemy.orm import Session

    from app.db import utcnow
    from app.models import Booking, BookingEvent, Slot, User
    url = f"sqlite:///{tmp_path}/expiry.db"
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "0009")
    eng = make_engine(url)
    with Session(eng) as db, db.begin():
        user = User(google_sub="test", email="test@example.test", role="professor")
        db.add(user)
        db.flush()
        slot = Slot(start_at=utcnow(), end_at=utcnow() + timedelta(minutes=30), created_by_id=user.id)
        db.add(slot)
        db.flush()
        booking = Booking(slot_id=slot.id, student_id=user.id, created_by_id=user.id, professor_note="private fixture")
        db.add(booking)
        db.flush()
        db.add(BookingEvent(booking_id=booking.id, actor_id=user.id, action="book", detail="preserve event"))
        bid = booking.id
    command.upgrade(cfg, "head")
    with Session(eng) as db, db.begin():
        booking = db.get(Booking, bid)
        assert booking.professor_note == "private fixture"
        assert booking.status == "booked"  # schema migration alone never changes outcomes
        assert db.query(BookingEvent).filter_by(booking_id=bid).one().detail == "preserve event"
        booking.status = "expired"
    import pytest
    with pytest.raises(RuntimeError, match="Cannot downgrade"):
        command.downgrade(cfg, "0009")
    with eng.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_key_check")).all() == []
    eng.dispose()
