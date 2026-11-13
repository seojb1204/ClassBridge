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
    assert clients['admin'].get('/api/inbox').status_code == 403
    assert clients['s1'].put(f"/api/inbox/{item['id']}/read").status_code == 403


def test_scoped_deduplicated_and_transactional(app, clients):
    with app.state.SessionLocal() as db:
        enqueue(db, 'suggestion-day-2026-11-13', 'suggestion')
        enqueue(db, 'suggestion-day-2026-11-13', 'suggestion')
        db.commit()
        rows = db.scalars(select(InboxNotification)).all()
        assert len(rows) == 1
        first_id = rows[0].id
        enqueue(db, 'rollback-test', 'created')
        db.rollback()
        assert len(db.scalars(select(InboxNotification)).all()) == 1
        user = db.scalar(select(User).where(User.email == 's2@test.ac.kr'))
        user.role = 'professor'
        db.commit()
    other = login(app, 's2@test.ac.kr')
    assert other.get('/api/inbox').json() == {'items': [], 'unread': 0}
    assert other.put(f'/api/inbox/{first_id}/read').status_code == 404
    with app.state.SessionLocal() as db:
        enqueue(db, 'new-event', 'changed')
        db.commit()
        assert len(db.scalars(select(InboxNotification)).all()) == 3


def test_inactive_professor_gets_no_new_rows(app, clients):
    with app.state.SessionLocal() as db:
        professor = db.scalar(select(User).where(User.role == 'professor'))
        professor.is_active = False
        db.flush()
        enqueue(db, 'inactive', 'created')
        db.commit()
        assert not db.scalars(select(InboxNotification)).all()


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
        row = db.scalar(select(InboxNotification))
        nid = row.id
    assert clients['prof'].get('/api/inbox').json() == {'items': [], 'unread': 0}
    assert clients['prof'].put(f'/api/inbox/{nid}/read').status_code == 404
    with app.state.SessionLocal() as db:
        db.get(InboxNotification, nid).available_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert clients['prof'].get('/api/inbox').json()['unread'] == 1
    assert clients['prof'].put(f'/api/inbox/{nid}/read').status_code == 200
