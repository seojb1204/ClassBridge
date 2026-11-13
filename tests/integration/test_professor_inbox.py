import pytest
from sqlalchemy import select

from app.models import InboxNotification, User
from app.services.inbox import enqueue
from tests.conftest import login, make_slots


def test_booking_inbox_without_external_channels(app, clients):
    assert not app.state.settings.push_enabled
    assert not app.state.settings.gmail_notifications_enabled
    sid = make_slots(clients['prof'])[0]
    response = clients['s1'].post('/api/bookings', json={'slot_id': sid, 'topic': 'private topic'})
    assert response.status_code == 201
    result = clients['prof'].get('/api/inbox').json()
    assert result['unread'] == 1
    item = result['items'][0]
    assert item['kind'] == 'created' and item['read'] is False
    assert '학생1' not in str(result) and 'private topic' not in str(result)
    assert 'event_key' not in item and 'created_at' not in item
    assert clients['prof'].put(f"/api/inbox/{item['id']}/read").status_code == 200
    assert clients['prof'].put(f"/api/inbox/{item['id']}/read").status_code == 200
    assert clients['prof'].get('/api/inbox').json()['unread'] == 0
    assert clients['s1'].get('/api/inbox').status_code == 403
    assert clients['admin'].get('/api/inbox').status_code == 200
    assert clients['s1'].put(f"/api/inbox/{item['id']}/read").status_code == 403


def test_scoped_deduplicated_and_transactional(app, clients):
    with app.state.SessionLocal() as db:
        enqueue(db, 'suggestion-day-2026-11-13', 'suggestion')
        enqueue(db, 'suggestion-day-2026-11-13', 'suggestion')
        db.commit()
        rows = db.scalars(select(InboxNotification)).all()
        assert len(rows) == 2
        first_id = next(r.id for r in rows if r.recipient_id == clients['prof'].me['id'])
        enqueue(db, 'rollback-test', 'created')
        db.rollback()
        assert len(db.scalars(select(InboxNotification)).all()) == 2
        user = db.scalar(select(User).where(User.email == 's2@test.ac.kr'))
        user.role = 'professor'
        db.commit()
    other = login(app, 's2@test.ac.kr')
    assert other.get('/api/inbox').json() == {'items': [], 'unread': 0, 'has_more': False, 'next_before_id': None}
    assert other.put(f'/api/inbox/{first_id}/read').status_code == 404
    with app.state.SessionLocal() as db:
        enqueue(db, 'new-event', 'changed')
        db.commit()
        assert len(db.scalars(select(InboxNotification)).all()) == 5


def test_inactive_professor_gets_no_new_rows(app, clients):
    with app.state.SessionLocal() as db:
        professor = db.scalar(select(User).where(User.role == 'professor'))
        professor.is_active = False
        db.flush()
        enqueue(db, 'inactive', 'created')
        db.commit()
        assert not db.scalars(select(InboxNotification).where(
            InboxNotification.recipient_id == professor.id)).all()


def test_inbox_migration_preserves_data_and_refuses_loss(tmp_path):
    import pytest
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.db import make_engine
    cfg = Config('alembic.ini')
    cfg.attributes['database_url'] = f'sqlite:///{tmp_path}/inbox.db'
    command.upgrade(cfg, '0010')
    engine = make_engine(cfg.attributes['database_url'])
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id,google_sub,email,name,role,is_active,created_at) "
                          "VALUES (1,'test','prof@example.test','private','professor',1,'2026-11-01')"))
    command.upgrade(cfg, 'head')
    with engine.begin() as conn:
        assert conn.execute(text('SELECT count(*) FROM inbox_notifications')).scalar() == 0
        assert conn.execute(text('SELECT name FROM users WHERE id=1')).scalar() == 'private'
        conn.execute(text("INSERT INTO inbox_notifications (recipient_id,event_key,kind,created_on,available_at) "
                          "VALUES (1,'test','created','2026-11-13','2026-11-13')"))
    with pytest.raises(RuntimeError, match='Cannot downgrade'):
        command.downgrade(cfg, '0010')
    with engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM inbox_notifications')).scalar() == 1
        assert conn.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0011'
        assert conn.execute(text('PRAGMA foreign_key_check')).all() == []
    engine.dispose()


def test_delayed_suggestion_not_visible_or_markable(app, clients):
    from datetime import timedelta

    from app.db import utcnow
    with app.state.SessionLocal() as db:
        enqueue(db, 'delayed', 'suggestion', available_at=utcnow() + timedelta(minutes=10))
        db.commit()
        row = db.scalar(select(InboxNotification).where(
            InboxNotification.recipient_id == clients['prof'].me['id']))
        nid = row.id
    assert clients['prof'].get('/api/inbox').json() == {'items': [], 'unread': 0, 'has_more': False, 'next_before_id': None}
    assert clients['prof'].put(f'/api/inbox/{nid}/read').status_code == 404
    with app.state.SessionLocal() as db:
        db.get(InboxNotification, nid).available_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert clients['prof'].get('/api/inbox').json()['unread'] == 1
    assert clients['prof'].put(f'/api/inbox/{nid}/read').status_code == 200


def test_admin_inbox_is_private_and_does_not_mark_professors_read(app, clients):
    sid = make_slots(clients['prof'])[0]
    assert clients['s1'].post('/api/bookings', json={'slot_id': sid}).status_code == 201
    prof_item = clients['prof'].get('/api/inbox').json()['items'][0]
    admin_result = clients['admin'].get('/api/inbox').json()
    assert admin_result['unread'] == 1
    admin_item = admin_result['items'][0]
    assert admin_item['id'] != prof_item['id']
    assert clients['admin'].put(f"/api/inbox/{prof_item['id']}/read").status_code == 404
    assert clients['prof'].put(f"/api/inbox/{admin_item['id']}/read").status_code == 404
    assert clients['admin'].put(f"/api/inbox/{admin_item['id']}/read").status_code == 200
    assert clients['admin'].get('/api/inbox').json()['unread'] == 0
    assert clients['prof'].get('/api/inbox').json()['unread'] == 1


def test_admin_suggestion_immediate_and_permission_revocation(app, clients):
    from app.db import utcnow
    from app.services import suggestion_service
    now = utcnow()
    with app.state.SessionLocal() as db:
        suggestion_service.save(db, 'other', 'private synthetic suggestion', False, now)
        row = db.scalar(select(InboxNotification).where(
            InboxNotification.recipient_id == clients['admin'].me['id']))
        nid = row.id
        assert row.available_at == now
    result = clients['admin'].get('/api/inbox').json()
    assert result['unread'] == 1
    assert 'private synthetic suggestion' not in str(result)
    with app.state.SessionLocal.begin() as db:
        user = db.get(User, clients['admin'].me['id'])
        user.role = 'student'
    assert clients['admin'].get('/api/inbox').status_code == 403
    assert clients['admin'].put(f'/api/inbox/{nid}/read').status_code == 403


def test_inactive_admin_gets_no_new_notices_or_access(app, clients):
    with app.state.SessionLocal.begin() as db:
        admin = db.get(User, clients['admin'].me['id'])
        admin.is_active = False
        db.flush()
        enqueue(db, 'inactive-admin-test', 'created')
        assert not db.scalars(select(InboxNotification).where(
            InboxNotification.recipient_id == admin.id)).all()
    assert clients['admin'].get('/api/inbox').status_code == 401


@pytest.mark.parametrize("role", ["prof", "admin"])
def test_arrival_order_ties_and_future_boundary(app, clients, monkeypatch, role):
    from datetime import timedelta

    from app.db import utcnow
    now = utcnow()
    monkeypatch.setattr('app.routers.inbox.utcnow', lambda: now)
    with app.state.SessionLocal.begin() as db:
        enqueue(db, 'delayed-created-first', 'suggestion', available_at=now)
        enqueue(db, 'later-id-earlier-arrival', 'created', available_at=now - timedelta(minutes=2))
        enqueue(db, 'tied-arrival', 'changed', available_at=now)
        enqueue(db, 'not-due', 'suggestion', available_at=now + timedelta(microseconds=1))
        rows = list(db.scalars(select(InboxNotification).where(
            InboxNotification.recipient_id == clients[role].me['id']).order_by(InboxNotification.id)))
        ids = [r.id for r in rows]
    result = clients[role].get('/api/inbox').json()
    assert [r['id'] for r in result['items']] == [ids[2], ids[0], ids[1]]
    assert result['unread'] == 3
    assert all('available_at' not in r and 'event_key' not in r for r in result['items'])
    assert clients[role].get(f'/api/inbox?before_id={ids[3]}').status_code == 404
    assert clients[role].put(f'/api/inbox/{ids[3]}/read').status_code == 404
    assert clients['admin' if role == 'prof' else 'prof'].get(f'/api/inbox?before_id={ids[0]}').status_code == 404


@pytest.mark.parametrize("role", ["prof", "admin"])
def test_cursor_reaches_old_unread_and_stays_stable_after_new_arrival(app, clients, role):
    from datetime import timedelta

    from app.db import utcnow
    now = utcnow()
    with app.state.SessionLocal.begin() as db:
        for i in range(105):
            enqueue(db, f'pagination-{i}', 'created', available_at=now - timedelta(seconds=i + 1))
        expected = [r.id for r in db.scalars(select(InboxNotification).where(
            InboxNotification.recipient_id == clients[role].me['id']).order_by(
                InboxNotification.available_at.desc(), InboxNotification.id.desc()))]
    first = clients[role].get('/api/inbox').json()
    assert len(first['items']) == 100 and first['has_more']
    cursor = first['next_before_id']
    with app.state.SessionLocal.begin() as db:
        enqueue(db, 'new-arrival-between-pages', 'changed', available_at=now)
    rest = clients[role].get(f'/api/inbox?before_id={cursor}').json()
    assert [r['id'] for r in first['items'] + rest['items']] == expected
    assert rest['has_more'] is False and rest['next_before_id'] is None
    oldest = rest['items'][-1]['id']
    assert clients[role].put(f'/api/inbox/{oldest}/read').status_code == 200
    unread = clients[role].get(f'/api/inbox?before_id={cursor}&unread_only=true').json()
    assert oldest not in [r['id'] for r in unread['items']]
    assert unread['unread'] == 105  # Includes the newer arrival, excludes only the read row.
    assert clients[role].get('/api/inbox?limit=0').status_code == 422
    assert clients[role].get('/api/inbox?limit=101').status_code == 422
    assert clients[role].get('/api/inbox?before_id=0').status_code == 422


def test_midnight_arrival_date_is_not_enqueue_day(app, clients, monkeypatch):
    from datetime import date, datetime, timezone

    now = datetime(2026, 11, 14, 15, 5, tzinfo=timezone.utc)  # KST Nov 15, 00:05.
    monkeypatch.setattr('app.routers.inbox.utcnow', lambda: now)
    with app.state.SessionLocal.begin() as db:
        db.add(InboxNotification(recipient_id=clients['prof'].me['id'],
            event_key='midnight-arrival', kind='suggestion', created_on=date(2026, 11, 14),
            available_at=now))
    item = clients['prof'].get('/api/inbox').json()['items'][0]
    assert item['created_on'] == '2026-11-14'
    assert item['arrived_on'] == '2026-11-15'
    assert item['arrived_at'] == '2026-11-15T00:05:00+09:00'
    assert 'available_at' not in item


def test_second_precision_order_within_displayed_minute(app, clients, monkeypatch):
    from datetime import datetime, timezone

    now = datetime(2026, 11, 13, 1, 2, 59, tzinfo=timezone.utc)
    monkeypatch.setattr('app.routers.inbox.utcnow', lambda: now)
    with app.state.SessionLocal.begin() as db:
        enqueue(db, 'newer-second-first-insert', 'suggestion', available_at=now)
        enqueue(db, 'older-second-later-insert', 'created', available_at=now.replace(second=1))
    items = clients['prof'].get('/api/inbox').json()['items']
    assert [i['arrived_at'] for i in items] == ['2026-11-13T10:02:59+09:00', '2026-11-13T10:02:01+09:00']


@pytest.mark.parametrize('role', ['prof', 'admin'])
def test_read_all_is_private_available_only_and_idempotent(app, clients, role):
    from datetime import timedelta

    from app.db import utcnow
    with app.state.SessionLocal.begin() as db:
        for i in range(7):
            enqueue(db, f'read-all-{i}', 'created')
        enqueue(db, 'read-all-future', 'suggestion', available_at=utcnow() + timedelta(days=1))
    assert clients[role].put('/api/inbox/read-all').json() == {'ok': True, 'unread': 0}
    assert clients[role].put('/api/inbox/read-all').json() == {'ok': True, 'unread': 0}
    assert all(i['read'] for i in clients[role].get('/api/inbox').json()['items'])
    assert clients['admin' if role == 'prof' else 'prof'].get('/api/inbox').json()['unread'] == 7
    with app.state.SessionLocal() as db:
        future = db.scalar(select(InboxNotification).where(InboxNotification.event_key == 'read-all-future',
            InboxNotification.recipient_id == clients[role].me['id']))
        assert future.read_at is None
    assert clients['s1'].put('/api/inbox/read-all').status_code == 403
    clients[role].headers.pop('X-CSRF-Token')
    assert clients[role].put('/api/inbox/read-all').status_code == 403
