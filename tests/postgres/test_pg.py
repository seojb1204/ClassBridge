"""실제 PostgreSQL에서의 마이그레이션·동시성 검증. TEST_PG_URL 미설정 시 건너뛴다.

SQLite 테스트 결과로 PostgreSQL 동작을 보증하지 않기 위해 별도로 실행한다.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from app.core.errors import AppError, Conflict
from app.db import utcnow
from app.models import Booking, Participation, Response, Slot, User
from app.services import booking_service, survey_service, user_service
from app.timeutil import kst_date
from tests.conftest import ADMIN, PG_URL, login, make_settings, make_slots

pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_PG_URL 미설정")


@pytest.mark.parametrize("revision", [0, 1])
def test_announcement_concurrent_publish_has_one_winner(pg_app, revision):
    from types import SimpleNamespace

    from app.models import AppSetting, AuditLog
    from app.routers.announcement import KEY, AnnouncementIn, put_announcement

    client = login(pg_app, ADMIN)
    actor = SimpleNamespace(id=client.me["id"])
    if revision:
        with pg_app.state.SessionLocal() as db:
            put_announcement(AnnouncementIn(title="초기", body="내용", published=False, revision=0), actor, db)

    def write(index):
        with pg_app.state.SessionLocal() as db:
            put_announcement(AnnouncementIn(title=f"공지 {index}", body="내용", published=True,
                                            revision=revision), actor, db)

    results = _race(2, write)
    assert sorted(results) == ["conflict", "ok"], results
    with pg_app.state.SessionLocal() as db:
        assert db.get(AppSetting, KEY).value["revision"] == revision + 1
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.action == "announcement.update")) == revision + 1


def _alembic(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = url
    return cfg


def test_anonymous_survey_concurrent_duplicate(pg_app):
    from app.models import GuestParticipation
    from tests.integration.test_public_surveys import create

    p = login(pg_app, ADMIN)
    survey = create(p)
    answers = {str(survey["questions"][0]["id"]): "개선 의견"}

    def write(_):
        with pg_app.state.SessionLocal() as db:
            survey_service.submit(db, None, survey["id"], answers, browser_hash="a" * 64)

    assert sorted(_race(2, write)) == ["already_participated", "ok"]
    with pg_app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(GuestParticipation)) == 1
        assert db.scalar(select(func.count()).select_from(Response)) == 1


# Supabase의 기본 상태를 흉내 낸다: anon·authenticated 역할이 있고,
# postgres가 public에 만드는 테이블·시퀀스에 이 역할들의 권한이 자동으로 붙는다.
SUPABASE_LIKE_SETUP = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
GRANT USAGE ON SCHEMA public TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated;
"""


@pytest.fixture
def pg_app():
    from app.main import create_app
    app = create_app(make_settings(PG_URL))
    with app.state.engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        conn.execute(text(SUPABASE_LIKE_SETUP))
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


def test_concurrent_open_slot_creation_cannot_overlap(pg_app):
    """Concurrent professor/admin requests must not create overlapping open slots."""
    prof = login(pg_app, "prof@test.ac.kr")
    prof_id = prof.me["id"]
    day = kst_date(utcnow()) + timedelta(days=2)
    spec = booking_service.SlotSpec(start_date=day, start_time=time(10, 0),
                                    end_time=time(10, 30), duration_minutes=30)

    def attempt(_):
        db = pg_app.state.SessionLocal()
        try:
            booking_service.create_slots(db, _user(db, prof_id), spec)
        finally:
            db.close()

    results = _race(2, attempt)
    assert results.count("ok") == 1, results
    assert results.count("slot_overlap") == 1, results
    db = pg_app.state.SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(Slot).where(Slot.status == "open")).scalar()
        assert count == 1
    finally:
        db.close()


def test_replacing_unbooked_slots_preserves_postgres_overlap_constraint(pg_app):
    """Replacing unreserved time keeps the old rows and the exclusion invariant."""
    professor = login(pg_app, "prof@test.ac.kr")
    old = make_slots(professor, start="10:00", end="11:00", duration=30)
    spec = {
        "start_date": kst_date(utcnow()).__add__(timedelta(days=2)).isoformat(),
        "start_time": "10:00", "end_time": "11:00", "duration_minutes": 60,
    }
    preview = professor.post("/api/slots/preview", json=spec)
    assert preview.status_code == 200, preview.text
    assert sorted(preview.json()["overlap_ids"]) == sorted(old)
    result = professor.post("/api/slots/replace", json={
        **spec, "expected_overlap_ids": preview.json()["overlap_ids"],
    })
    assert result.status_code == 200, result.text
    assert result.json()["replaced"] == 2
    with pg_app.state.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM slots WHERE status='open'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM slots WHERE status='cancelled'")).scalar() == 2
        assert conn.execute(text(
            "SELECT count(*) FROM pg_constraint WHERE conname='ex_slots_no_overlap_open'"
        )).scalar() == 1


def test_database_rejects_overlapping_open_slots(pg_app):
    """The DB rule still applies if API/application overlap checks are bypassed."""
    prof = login(pg_app, "prof@test.ac.kr")
    sid = make_slots(prof, start="10:00", end="10:30")[0]
    with pytest.raises(Exception, match="ex_slots_no_overlap_open"):
        with pg_app.state.engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO slots
                    (start_at, end_at, kind, capacity, booked_count, status,
                     location, note, created_by_id, created_at)
                SELECT start_at + INTERVAL '5 minutes',
                       end_at + INTERVAL '5 minutes', kind, capacity, 0, 'open',
                       '', '', created_by_id, NOW()
                FROM slots WHERE id = :sid
            """), {"sid": sid})


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


# ── Supabase 공개 API 경로 차단 (마이그레이션 0002) ──

def _public_tables(conn):
    return [r[0] for r in conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))]


def test_supabase_api_roles_have_no_access(pg_app):
    with pg_app.state.engine.connect() as conn:
        tables = _public_tables(conn)
        assert len(tables) >= 13
        for t in tables:
            for role in ("anon", "authenticated"):
                for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    assert conn.execute(text("SELECT has_table_privilege(:r, :t, :p)"),
                                        {"r": role, "t": f"public.{t}", "p": priv}).scalar() is False, (role, t, priv)
        seqs = [r[0] for r in conn.execute(text(
            "SELECT sequencename FROM pg_sequences WHERE schemaname='public'"))]
        for sq in seqs:
            assert conn.execute(text("SELECT has_sequence_privilege('anon', :s, 'USAGE')"),
                                {"s": f"public.{sq}"}).scalar() is False


def test_every_public_table_has_rls(pg_app):
    """앞으로 테이블을 추가하는 마이그레이션이 RLS를 빠뜨리면 이 테스트가 실패한다."""
    with pg_app.state.engine.connect() as conn:
        missing = [r[0] for r in conn.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"))]
    assert missing == []


def test_anon_role_is_denied_in_practice(pg_app):
    """REST API가 쓰는 anon 역할로 실제 조회하면 거부된다."""
    login(pg_app, "anon-check@test.ac.kr")
    with pg_app.state.engine.connect() as conn:
        conn.execute(text("SET ROLE anon"))
        with pytest.raises(Exception) as e:
            conn.execute(text("SELECT email FROM users"))
        assert "permission denied" in str(e.value)
        conn.rollback()


def test_future_tables_get_no_api_grants(pg_app):
    """기본 권한 회수 확인: 마이그레이션 이후 새로 만든 테이블에도 anon 권한이 붙지 않는다."""
    with pg_app.state.engine.begin() as conn:
        conn.execute(text("CREATE TABLE public.future_probe (id int)"))
        granted = conn.execute(text("SELECT has_table_privilege('anon', 'public.future_probe', 'SELECT')")).scalar()
        conn.execute(text("DROP TABLE public.future_probe"))
    assert granted is False


def test_app_still_works_with_rls(pg_app):
    """앱은 테이블 소유자로 접속하므로 RLS의 영향을 받지 않는다."""
    prof = login(pg_app, "prof@test.ac.kr")
    sid = make_slots(prof, start="11:00", end="11:30")[0]
    s = login(pg_app, "rls-student@test.ac.kr")
    assert s.post("/api/bookings", json={"slot_id": sid}).status_code == 201
    assert len(s.get("/api/bookings/mine").json()) == 1


def test_non_superuser_owner_bypasses_rls(pg_app):
    """Supabase의 postgres는 슈퍼유저가 아니라 테이블 소유자다. 소유자는 FORCE가 없으면 RLS를 우회하는지 확인."""
    login(pg_app, "owner-check@test.ac.kr")
    with pg_app.state.engine.connect() as conn:
        forced = conn.execute(text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relforcerowsecurity")).scalar()
        assert forced == 0
        conn.execute(text("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='cb_owner_probe') "
                          "THEN CREATE ROLE cb_owner_probe NOSUPERUSER NOBYPASSRLS; END IF; END $$"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO cb_owner_probe"))
        conn.execute(text("ALTER TABLE users OWNER TO cb_owner_probe"))
        conn.execute(text("SET ROLE cb_owner_probe"))
        n = conn.execute(text("SELECT count(*) FROM users")).scalar()
        conn.rollback()  # 소유자 변경 되돌림
    assert n >= 1
