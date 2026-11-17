from datetime import timedelta

from sqlalchemy import select

from app.db import utcnow
from app.models import InboxNotification
from app.services.inbox import enqueue
from tests.conftest import make_slots


def test_target_owned_booking_and_cancelled(app, clients):
    sid = make_slots(clients['prof'])[0]
    created = clients['s1'].post('/api/bookings', json={'slot_id': sid, 'topic': 'specific target'})
    assert created.status_code == 201
    nid = clients['prof'].get('/api/inbox').json()['items'][0]['id']
    row = clients['prof'].get(f'/api/inbox/{nid}/target')
    assert row.status_code == 200
    booking = row.json()['booking']
    assert booking['slot']['id'] == sid and booking['topic'] == 'specific target'
    assert row.json()['notification']['url'] == f'/#/inbox/{nid}'
    assert clients['s1'].get(f'/api/inbox/{nid}/target').status_code == 403
    assert clients['admin'].get(f'/api/inbox/{nid}/target').status_code == 404
    assert clients['prof'].post(f"/api/bookings/{booking['id']}/cancel", json={'reason': 'test'}).status_code == 200
    assert clients['prof'].get(f'/api/inbox/{nid}/target').json()['booking']['status'] == 'cancelled'


def test_legacy_missing_event_and_future_safe(app, clients):
    with app.state.SessionLocal() as db:
        for key in ('legacy', 'booking-event-999999', 'booking-event-1bad'):
            enqueue(db, key, 'created')
        enqueue(db, 'future', 'created', available_at=utcnow() + timedelta(days=1))
        db.commit()
        rows = list(db.scalars(select(InboxNotification).where(InboxNotification.recipient_id == clients['prof'].me['id'])))
        for row in rows:
            result = clients['prof'].get(f'/api/inbox/{row.id}/target')
            if row.event_key == 'future':
                assert result.status_code == 404
            else:
                assert result.status_code == 200
                assert result.json()['unavailable'] and result.json()['booking'] is None


def test_reminder_body_and_suggestion_destination(app, clients):
    from app.timeutil import kst_date
    with app.state.SessionLocal() as db:
        row = InboxNotification(recipient_id=clients['prof'].me['id'], event_key='reminder-test',
            kind='custom_reminder', message='물 사야 해요', created_on=kst_date(utcnow()), available_at=utcnow())
        db.add(row)
        enqueue(db, 'suggestion-test', 'suggestion')
        db.commit()
        nid = row.id
    result = clients['prof'].get(f'/api/inbox/{nid}/target').json()
    assert result['type'] == 'custom_reminder' and result['notification']['body'] == '물 사야 해요'
    items = clients['prof'].get('/api/inbox').json()['items']
    assert next(x for x in items if x['kind'] == 'suggestion')['url'] == '/#/suggestions'
