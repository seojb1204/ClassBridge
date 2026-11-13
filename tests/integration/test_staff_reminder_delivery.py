"""Synthetic deliveries only: no external push or email calls."""
import json
from datetime import timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import utcnow
from app.infra.push import PushSender
from app.models import Notification, User
from app.models.staff_reminder import StaffReminder
from app.services import staff_reminders
from app.services.notifications import deliver_one, next_worker_delay
from tests.integration.test_push import enable, subscription


def schedule(app, clients, when):
    identifier = str(uuid4())
    with app.state.SessionLocal() as db:
        staff_reminders.create(db, identifier, clients['prof'].me['id'], 'Synthetic scheduled message', when,
                               clients['admin'].me['id'])
    return identifier


def test_future_deadline_planned_even_without_external_channels(app, clients):
    now = utcnow()
    schedule(app, clients, now + timedelta(seconds=41))
    assert next_worker_delay(app.state.SessionLocal, app.state.settings, now) == 41
    assert next_worker_delay(app.state.SessionLocal, app.state.settings, now + timedelta(seconds=42)) == .1


@pytest.mark.parametrize('revoke', ['none', 'role', 'optout', 'wrong-recipient'])
def test_scheduled_push_rechecks_authoritative_recipient_and_permission(app, clients, monkeypatch, revoke):
    settings = enable(app)
    clients['prof'].post('/api/admin/push-subscription', json=subscription())
    due = utcnow() + timedelta(minutes=1)
    identifier = schedule(app, clients, due)
    with app.state.SessionLocal() as db:
        staff_reminders.enqueue_due(db, due)
        row = db.scalar(select(Notification).where(Notification.payload['kind'].as_string() == 'custom_reminder'))
        assert row and row.payload == {'kind': 'custom_reminder', 'reminder_id': identifier}
        prof = db.get(User, clients['prof'].me['id'])
        if revoke == 'role':
            prof.role = 'admin'
        elif revoke == 'optout':
            prof.alert_preferences = {'instant': False}
        elif revoke == 'wrong-recipient':
            db.get(StaffReminder, identifier).recipient_id = clients['admin'].me['id']
        db.commit()
    monkeypatch.setattr('app.db.utcnow', lambda: due)
    send = Mock(return_value=Mock(status_code=201))
    monkeypatch.setattr('pywebpush.webpush', send)
    assert deliver_one(app.state.SessionLocal, PushSender(settings, app.state.SessionLocal), settings,
                       now=due, channel='push')
    if revoke == 'none':
        data = json.loads(send.call_args.kwargs['data'])
        assert data['body'] == 'Synthetic scheduled message' and data['url'] == '/#/inbox'
        send.assert_called_once()
    else:
        send.assert_not_called()
    assert not deliver_one(app.state.SessionLocal, Mock(), settings, now=due, channel='push')


def test_independent_scheduled_messages_not_blocked_by_old_uncertain_chain(app, clients):
    settings = enable(app)
    clients['prof'].post('/api/admin/push-subscription', json=subscription())
    due = utcnow() + timedelta(minutes=1)
    schedule(app, clients, due)
    schedule(app, clients, due)
    with app.state.SessionLocal() as db:
        staff_reminders.enqueue_due(db, due)
        rows = list(db.scalars(select(Notification).order_by(Notification.id)))
        assert len(rows) == 2
        rows[0].status = 'uncertain'
        rows[1].chain_id = rows[0].chain_id
        db.commit()
    assert next_worker_delay(app.state.SessionLocal, settings, due) == .1
    sender = Mock()
    sender.send.return_value = 'synthetic accepted'
    assert deliver_one(app.state.SessionLocal, sender, settings, now=due, channel='push')
    sender.send.assert_called_once()
