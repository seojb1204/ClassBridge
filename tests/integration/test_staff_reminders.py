from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.db import utcnow
from app.models import InboxNotification, Notification, StaffReminder, User
from app.services import staff_reminders as svc


def body(clients):
    return {'id': str(uuid4()), 'recipient_id': clients['prof'].me['id'],
            'message': 'Synthetic private reminder', 'scheduled_at': (utcnow() + timedelta(hours=1)).isoformat()}


def test_create_scope_idempotence_validation_and_cancel(app, clients):
    payload = body(clients)
    api = '/api/admin/staff-reminders'
    for who in ('s1', 'prof'):
        assert clients[who].post(api, json=payload).status_code == 403
    admin = clients['admin']
    assert admin.post(api, json=payload).status_code == 201
    assert admin.post(api, json=payload).status_code == 201
    assert admin.post(api, json={**payload, 'message': 'different'}).status_code == 409
    assert len(admin.get(api).json()) == 1
    assert admin.post(api, json={**payload, 'id': str(uuid4()), 'recipient_id': clients['s1'].me['id']}).status_code == 400
    assert admin.post(api, json={**payload, 'id': str(uuid4()), 'scheduled_at': utcnow().isoformat()}).status_code == 400
    assert admin.post(api, json={**payload, 'id': str(uuid4()), 'scheduled_at': '2030-01-01T12:00:00'}).status_code == 422
    assert admin.post(api, json={**payload, 'id': str(uuid4()), 'message': 'x' * 241}).status_code == 422
    assert admin.put(f"{api}/{payload['id']}/cancel").status_code == 200
    assert admin.put(f"{api}/{payload['id']}/cancel").status_code == 200
    with app.state.SessionLocal() as db:
        assert svc.next_due(db) is None
        svc.enqueue_due(db, utcnow() + timedelta(days=1))
        assert not db.scalars(select(InboxNotification)).all()


def test_due_private_offline_idempotent_and_no_external(app, clients):
    payload = body(clients)
    assert clients['admin'].post('/api/admin/staff-reminders', json=payload).status_code == 201
    with app.state.SessionLocal() as db:
        row = db.get(StaffReminder, payload['id'])
        due = row.scheduled_at
        assert svc.next_due(db) == due
        svc.enqueue_due(db, due - timedelta(seconds=1))
        assert not db.scalars(select(InboxNotification)).all()
        svc.enqueue_due(db, due + timedelta(days=1))  # outage recovery, no grace loss
        svc.enqueue_due(db, due + timedelta(days=1))
        inbox = db.scalars(select(InboxNotification)).all()
        assert len(inbox) == 1 and inbox[0].recipient_id == clients['prof'].me['id']
        assert inbox[0].message == payload['message']
        assert not db.scalars(select(Notification)).all()
        assert svc.next_due(db) is None
    assert clients['admin'].put(f"/api/admin/staff-reminders/{payload['id']}/cancel").status_code == 409


def test_role_revocation_suppresses_due(app, clients):
    payload = body(clients)
    assert clients['admin'].post('/api/admin/staff-reminders', json=payload).status_code == 201
    with app.state.SessionLocal() as db:
        db.get(User, payload['recipient_id']).role = 'student'
        db.commit()
        svc.enqueue_due(db, utcnow() + timedelta(days=1))
        assert db.get(StaffReminder, payload['id']).cancelled_at is not None
        assert not db.scalars(select(InboxNotification)).all()


def test_due_failure_rolls_back_marker_and_inbox(app, clients, monkeypatch):
    payload = body(clients)
    clients['admin'].post('/api/admin/staff-reminders', json=payload)
    with app.state.SessionLocal() as db:
        def fail():
            raise RuntimeError('synthetic commit failure')
        monkeypatch.setattr(db, 'commit', fail)
        import pytest
        with pytest.raises(RuntimeError):
            svc.enqueue_due(db, utcnow() + timedelta(days=1))
        db.rollback()
    with app.state.SessionLocal() as db:
        assert db.get(StaffReminder, payload['id']).dispatched_at is None
        assert not db.scalars(select(InboxNotification)).all()


def test_additive_migration_preserves_inbox_and_guards_reminders(tmp_path):
    import pytest
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from app.db import make_engine
    cfg = Config('alembic.ini')
    cfg.attributes['database_url'] = f'sqlite:///{tmp_path}/scheduled.db'
    command.upgrade(cfg, '0011')
    eng = make_engine(cfg.attributes['database_url'])
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (id,google_sub,email,name,role,is_active,created_at) "
                       "VALUES (1,'fixture','p@example.test','Professor','professor',1,'2026-01-01')"))
        c.execute(text("INSERT INTO inbox_notifications (recipient_id,event_key,kind,created_on,available_at) "
                       "VALUES (1,'legacy','created','2026-01-01','2026-01-01')"))
    command.upgrade(cfg, 'head')
    with eng.begin() as c:
        assert c.execute(text('SELECT message FROM inbox_notifications')).one() == (None,)
        assert c.execute(text('SELECT count(*) FROM staff_reminders')).scalar() == 0
        c.execute(text("INSERT INTO staff_reminders (id,recipient_id,message,scheduled_at,created_at) "
                       "VALUES ('fixture',1,'Synthetic reminder','2030-01-01','2026-01-01')"))
    with pytest.raises(RuntimeError, match='Cannot downgrade'):
        command.downgrade(cfg, '0011')
    with eng.connect() as c:
        assert c.execute(text('SELECT count(*) FROM staff_reminders')).scalar() == 1
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar() == '0012'
        assert c.execute(text('PRAGMA foreign_key_check')).all() == []
    eng.dispose()
