# ruff: noqa: F811
"""Real PostgreSQL only: calendar exclusion in both commit orders and real races."""
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models import Booking, Lecture, Slot, User
from app.routers.lectures import LectureInput, create
from app.services import booking_service
from app.services.lecture_policy import lock_calendar
from tests.conftest import PG_URL, PROF, future_day, login, make_slots
from tests.postgres.test_pg import _race, pg_app  # noqa: F401

pytestmark = pytest.mark.skipif(not PG_URL, reason='TEST_PG_URL 미설정')


def _lecture():
    return LectureInput(title='강의', date=future_day(), start_time='10:00', end_time='11:00')


@pytest.mark.parametrize('first', ['lecture', 'booking'])
def test_calendar_waiter_rechecks_after_commit(pg_app, first):
    p, s = login(pg_app, PROF), login(pg_app, 'student@test.ac.kr')
    slot_id = make_slots(p)[0]
    started = threading.Event()
    def action(kind, db):
        if kind == 'lecture':
            return create(_lecture(), SimpleNamespace(id=p.me['id']), db)
        return booking_service.book(db, db.get(User, s.me['id']), slot_id)
    def waiter():
        with pg_app.state.SessionLocal() as db:
            started.set()
            try:
                action('booking' if first == 'lecture' else 'lecture', db)
                return 'unexpected_success'
            except AppError as exc:
                return exc.code
    with pg_app.state.SessionLocal() as owner, ThreadPoolExecutor(1) as pool:
        lock_calendar(owner)
        future = pool.submit(waiter)
        assert started.wait(5)
        action(first, owner)  # Commits and releases the transaction advisory lock.
        assert future.result(timeout=10) == ('lecture_overlap' if first == 'lecture' else 'lecture_booking_overlap')
    with pg_app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lecture)) == (first == 'lecture')
        assert db.scalar(select(func.count()).select_from(Booking)) == (first == 'booking')
        assert db.get(Slot, slot_id).booked_count == (first == 'booking')


def test_simultaneous_lecture_vs_booking_one_winner(pg_app):
    p, s = login(pg_app, PROF), login(pg_app, 'student@test.ac.kr')
    slot = make_slots(p)[0]
    def attempt(index):
        with pg_app.state.SessionLocal() as db:
            if index:
                create(_lecture(), SimpleNamespace(id=p.me['id']), db)
            else:
                booking_service.book(db, db.get(User, s.me['id']), slot)
    results = _race(2, attempt)
    assert results.count('ok') == 1, results
    assert set(results) <= {'ok', 'lecture_overlap', 'lecture_booking_overlap'}, results


def test_simultaneous_overlapping_lectures_one_winner(pg_app):
    p = login(pg_app, PROF)
    def attempt(index):
        with pg_app.state.SessionLocal() as db:
            create(_lecture(), SimpleNamespace(id=p.me['id']), db)
    assert sorted(_race(2, attempt)) == ['lecture_overlap', 'ok']


def test_populated_lecture_downgrade_refuses_data_loss(pg_app):
    from alembic import command
    from sqlalchemy import text

    from tests.postgres.test_pg import _alembic
    p = login(pg_app, PROF)
    assert p.post('/api/lectures', json={
        'title': '보존 검증', 'date': future_day().isoformat(),
        'start_time': '10:00', 'end_time': '11:00'}).status_code == 201
    with pytest.raises(RuntimeError, match='preserve lecture data'):
        command.downgrade(_alembic(PG_URL), '0012')
    with pg_app.state.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM lectures')).scalar() == 1
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0013'
