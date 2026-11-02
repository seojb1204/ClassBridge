"""실제 PostgreSQL에서의 마이그레이션·동시성 검증. TEST_PG_URL 미설정 시 건너뛴다.

SQLite 테스트 결과로 PostgreSQL 동작을 보증하지 않기 위해 별도로 실행한다.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.core.errors import AppError, Conflict
from app.models import Booking, Participation, Response, Slot, User
from app.services import booking_service, survey_service, user_service
from tests.conftest import ADMIN, PG_URL, login, make_settings, make_slots

pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_PG_URL 미설정")


def _alembic(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    return cfg


@pytest.fixture
def pg_app():
    from app.main import create_app
    app = create_app(make_settings(PG_URL))
    with app.state.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    command.upgrade(_alembic(PG_URL), "head")  # 스키마는 마이그레이션으로만 생성
    yield app
    app.state.engine.dispose()


def _race(n, fn):
    barrier = threading.Barrier(n)

    def run(i):
        barrier.wait()
        try:
            fn(i)
            return "ok"
        except AppError as e:
            return e.code
        except Exception as e:  # 예상치 못한 DB 오류(교착 등)도 기록
            return f"ERR:{type(e).__name__}"

    with ThreadPoolExecutor(n) as ex:
        return list(ex.map(run, range(n)))


def _students(app, n):
    return [login(app, f"pg{i}@test.ac.kr").me["id"] for i in range(n)]


def _user(db, uid):
    return db.get(User, uid)


def test_migration_matches_models_and_downgrades(pg_app):
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext

    from app.db import Base
    with pg_app.state.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], diff
    command.downgrade(_alembic(PG_URL), "base")
    with pg_app.state.engine.connect() as conn:
        tables = conn.execute(text("select count(*) from information_schema.tables where table_schema='public' "
                                   "and table_name <> 'alembic_version'")).scalar()
    assert tables == 0
    command.upgrade(_alembic(PG_URL), "head")


def test_concurrent_last_seat_individual(pg_app):
    prof = login(pg_app, "prof@test.ac.kr")
    sid = make_slots(prof, start="10:00", end="10:30")[0]
    ids = _students(pg_app, 12)

    def attempt(i):
        db = pg_app.state.SessionLocal()
        try:
            booking_service.book(db, _user(db, ids[i]), sid)
        finally:
            db.close()

    results = _race(12, attempt)
    assert results.count("ok") == 1, results
    assert all(r in ("ok", "slot_full") for r in results), results
    db = pg_app.state.SessionLocal()
    assert db.get(Slot, sid).booked_count == 1
    assert db.execute(select(func.count()).select_from(Booking).where(Booking.slot_id == sid)).scalar() == 1
    db.close()


def test_concurrent_group_capacity(pg_app):
    prof = login(pg_app, "prof@test.ac.kr")
    sid = make_slots(prof, start="14:00", end="15:00", duration=60, kind="group", capacity=5)[0]
    ids = _students(pg_app, 20)

    def attempt(i):
        db = pg_app.state.SessionLocal()
        try:
            booking_service.book(db, _user(db, ids[i]), sid)
        finally:
            db.close()

    results = _race(20, attempt)
    assert results.count("ok") == 5, results
    assert all(r in ("ok", "slot_full") for r in results), results
    db = pg_app.state.SessionLocal()
    active = db.execute(select(func.count()).select_from(Booking)
                        .where(Booking.slot_id == sid, Booking.status == "booked")).scalar()
    assert active == 5 and db.get(Slot, sid).booked_count == 5
    db.close()


def test_same_student_double_booking_race(pg_app):
    """앱 수준 사전 검사를 동시에 통과해도 부분 유니크 인덱스가 1건만 허용한다."""
    prof = login(pg_app, "prof@test.ac.kr")
    slots = make_slots(prof, start="10:00", end="13:00", duration=30)
    uid = _students(pg_app, 1)[0]

    def attempt(i):
        db = pg_app.state.SessionLocal()
        try:
            booking_service.book(db, _user(db, uid), slots[i])
        finally:
            db.close()

    results = _race(6, attempt)
    assert results.count("ok") == 1, results
    assert all(r in ("ok", "active_booking_exists") for r in results), results
    db = pg_app.state.SessionLocal()
    assert sum(s.booked_count for s in db.execute(select(Slot)).scalars()) == 1  # 좌석 누수 없음
    db.close()


def test_reschedule_vs_booking_race(pg_app):
    prof = login(pg_app, "prof@test.ac.kr")
    a_slot, target = make_slots(prof, start="10:00", end="11:00", duration=30)
    ida, idb = _students(pg_app, 2)
    db = pg_app.state.SessionLocal()
    old = booking_service.book(db, _user(db, ida), a_slot)
    db.close()

    def attempt(i):
        db = pg_app.state.SessionLocal()
        try:
            if i == 0:
                booking_service.reschedule(db, _user(db, ida), old.id, target)
            else:
                booking_service.book(db, _user(db, idb), target)
        finally:
            db.close()

    for _ in range(1):
        results = _race(2, attempt)
    assert results.count("ok") == 1, results
    db = pg_app.state.SessionLocal()
    t = db.get(Slot, target)
    a = db.get(Slot, a_slot)
    assert t.booked_count == 1
    a_active = db.execute(select(Booking).where(Booking.student_id == ida, Booking.status == "booked")).scalars().all()
    assert len(a_active) == 1  # A는 어느 쪽이든 정확히 1건 보유 (변경 실패 시 기존 예약 유지)
    assert a.booked_count == (1 if results[0] != "ok" else 0)
    db.close()


def test_concurrent_survey_double_submit(pg_app):
    prof = login(pg_app, "prof@test.ac.kr")
    r = prof.post("/api/surveys", json={"title": "s", "min_results": 1,
                                        "questions": [{"qtype": "scale5", "title": "만족", "required": True}]})
    sid, qid = r.json()["id"], r.json()["questions"][0]["id"]
    prof.post(f"/api/surveys/{sid}/publish")
    uid = _students(pg_app, 1)[0]

    def attempt(i):
        db = pg_app.state.SessionLocal()
        try:
            survey_service.submit(db, _user(db, uid), sid, {str(qid): 3})
        finally:
            db.close()

    results = _race(8, attempt)
    assert results.count("ok") == 1 and results.count("already_participated") == 7, results
    db = pg_app.state.SessionLocal()
    assert db.execute(select(func.count()).select_from(Participation)).scalar() == 1
    assert db.execute(select(func.count()).select_from(Response)).scalar() == 1
    db.close()


def test_concurrent_cross_demotion_keeps_an_admin(pg_app):
    a = login(pg_app, ADMIN)
    b = login(pg_app, "b2@test.ac.kr")
    a.put(f"/api/admin/users/{b.me['id']}/role", json={"role": "admin"})
    aid, bid = a.me["id"], b.me["id"]

    def attempt(i):
        db = pg_app.state.SessionLocal()
        try:
            actor, target = (aid, bid) if i == 0 else (bid, aid)
            user_service.change_role(db, _user(db, actor), target, "student")
        finally:
            db.close()

    results = _race(2, attempt)
    assert not any(r.startswith("ERR") for r in results), results  # 교착(Deadlock) 없음
    db = pg_app.state.SessionLocal()
    admins = db.execute(select(func.count()).select_from(User).where(User.role == "admin")).scalar()
    db.close()
    assert admins >= 1, results


def test_capacity_check_constraint_enforced_by_db(pg_app):
    prof = login(pg_app, "prof@test.ac.kr")
    sid = make_slots(prof, start="16:00", end="16:30")[0]
    with pg_app.state.engine.connect() as conn:
        with pytest.raises(Exception) as e:
            conn.execute(text("UPDATE slots SET booked_count = 2 WHERE id = :i"), {"i": sid})
        assert "ck_slots_booked_range" in str(e.value)


def test_service_conflict_type(pg_app):
    assert issubclass(Conflict, AppError)
