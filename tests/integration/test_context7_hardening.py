"""Regression checks use temporary SQLite and fake delivery, never a provider."""
from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.config import ConfigError, Settings, load_settings
from app.core.errors import Conflict
from app.db import utcnow
from app.models import Notification, Slot, User
from app.services import analysis_service, booking_service, notifications
from tests.conftest import make_slots
from tests.integration.test_notifications import enable


@pytest.mark.parametrize('env', ['prod', 'Production', 'staging', '', 'production '])
def test_unknown_environment_is_rejected(env, monkeypatch):
    with pytest.raises(ConfigError, match='APP_ENV'):
        Settings(env=env).validate()
    monkeypatch.setenv('APP_ENV', env)
    with pytest.raises(ConfigError, match='APP_ENV'):
        load_settings()


@pytest.mark.parametrize('kind', ['created', 'changed', 'cancelled', 'slot_changed', 'suggestion'])
@pytest.mark.parametrize('state', ['inactive', 'student', 'admin', 'missing'])
def test_all_gmail_kinds_recheck_professor_permission(app, clients, kind, state):
    settings = enable(app)
    sid = make_slots(clients['prof'])[0]
    assert clients['s1'].post('/api/bookings', json={'slot_id': sid}).status_code == 201
    with app.state.SessionLocal() as db:
        row = db.scalar(select(Notification))
        row.payload = {**row.payload, 'kind': kind}
        user = db.get(User, clients['prof'].me['id'])
        if state == 'inactive':
            user.is_active = False
        elif state == 'missing':
            row.recipient = 'missing@example.com'
        else:
            user.role = state
        db.commit()
    sender = Mock()
    assert notifications.deliver_one(app.state.SessionLocal, sender, settings)
    sender.send.assert_not_called()
    with app.state.SessionLocal() as db:
        row = db.scalar(select(Notification))
        assert (row.status, row.error_code) == ('skipped', 'recipient_permission_revoked')


def test_email_pause_after_claim_prevents_delivery(app, clients, monkeypatch):
    from app.repositories.settings import put
    from app.services.personal_alerts import EMAIL_PAUSED
    settings = enable(app)
    sid = make_slots(clients['prof'])[0]
    clients['s1'].post('/api/bookings', json={'slot_id': sid})
    original = notifications.claim
    def claim_then_pause(*args):
        row = original(*args)
        with app.state.SessionLocal() as db:
            put(db, EMAIL_PAUSED, True)
            db.commit()
        return row
    monkeypatch.setattr(notifications, 'claim', claim_then_pause)
    sender = Mock()
    assert notifications.deliver_one(app.state.SessionLocal, sender, settings)
    sender.send.assert_not_called()


def test_booking_refreshes_stale_slot_before_deadline_check(app, clients):
    from sqlalchemy import update
    sid = make_slots(clients['prof'])[0]
    with app.state.SessionLocal() as db:
        stale = db.get(Slot, sid)
        actor = db.get(User, clients['s1'].me['id'])
        # Independent SQL change represents data newer than this Session's identity map.
        now = utcnow()
        db.execute(update(Slot).where(Slot.id == sid).values(
            start_at=now + timedelta(minutes=5), end_at=now + timedelta(minutes=35))
            .execution_options(synchronize_session=False))
        assert stale.start_at > now + timedelta(minutes=30)
        with pytest.raises(Conflict) as error:
            booking_service.book(db, actor, sid, now=now)
        assert error.value.code == 'booking_deadline'


@pytest.mark.parametrize('raw', [None, [], {'themes': None}, {'themes': [None]},
    {'themes': [{'item_ids': None}]}, {'actions': None}, {'actions': [5]}, {'summary': None}])
def test_optional_external_analysis_bad_shapes_fall_back(app, monkeypatch, raw):
    monkeypatch.setattr(analysis_service, 'collect_texts', lambda *args: ['설명이 좋았어요'])
    client = Mock()
    client.analyze.return_value = raw
    with app.state.SessionLocal() as db:
        result = analysis_service.analyze(db, 'external', client, 'suggestions', None)
    assert result['engine'] == 'local-keyword'
    assert '대체' in result['notice']


def test_local_analysis_does_not_call_external_client(app, monkeypatch):
    monkeypatch.setattr(analysis_service, 'collect_texts', lambda *args: ['설명이 좋았어요'])
    client = Mock()
    with app.state.SessionLocal() as db:
        assert analysis_service.analyze(db, 'demo', client, 'suggestions', None)['engine'] == 'local-keyword'
    client.analyze.assert_not_called()
