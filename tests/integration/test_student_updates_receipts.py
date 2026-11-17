import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import Suggestion
from tests.conftest import make_slots


def test_student_updates_ownership_notes_and_racing_ack(clients):
    prof, student, other = (clients[k] for k in ('prof', 's1', 's2'))
    slots = make_slots(prof)
    b = prof.post('/api/bookings', json={'slot_id': slots[0], 'student_id': student.me['id']}).json()
    path = f"/api/bookings/{b['id']}"
    first = student.get('/api/bookings/mine').json()[0]
    assert first['unread_update']
    assert other.get(path + '/updates').status_code == 404
    assert other.post(path + f"/updates/{first['latest_update_id']}/read").status_code == 404
    assert prof.put(path + '/note', json={'note': 'STAFF PRIVATE'}).status_code == 200
    r = prof.post(path + '/reschedule', json={'new_slot_id': slots[1], 'reason': '일정 조정'})
    assert r.status_code == 200, r.text
    events = student.get(path + '/updates').json()
    assert events[-1]['action'] == 'rescheduled'
    assert '일정 조정' in events[-1]['detail']
    assert 'STAFF PRIVATE' not in str(events)
    assert student.post(path + f"/updates/{first['latest_update_id']}/read").status_code == 204
    assert student.get('/api/bookings/mine').json()[0]['unread_update']
    last = events[-1]['id']
    assert student.post(path + f'/updates/{last}/read').status_code == 204
    assert student.post(path + f'/updates/{last}/read').status_code == 204
    assert not student.get('/api/bookings/mine').json()[0]['unread_update']
    assert prof.post(path + '/cancel', json={'reason': '휴강'}).status_code == 200
    cancelled = student.get('/api/bookings/mine').json()[0]
    assert cancelled['status'] == 'cancelled' and cancelled['unread_update']


def test_self_booking_does_not_raise_staff_update(clients):
    slot = make_slots(clients['prof'])[0]
    assert clients['s1'].post('/api/bookings', json={'slot_id': slot}).status_code == 201
    assert not clients['s1'].get('/api/bookings/mine').json()[0]['unread_update']


def test_anonymous_receipt_private_reply_and_trash(app, clients):
    guest = TestClient(app)
    r = guest.post('/api/suggestions/anonymous', headers={'X-Anonymous-Submit': '1'},
                   json={'category': 'other', 'content': '비공개 질문'})
    assert r.status_code == 201, r.text
    token = r.json()['receipt_token']
    assert len(token) == 43
    result = guest.post('/api/suggestions/receipt', json={'token': token})
    assert result.status_code == 200 and result.headers['cache-control'] == 'no-store'
    item = result.json()
    assert not item['is_public'] and 'receipt_hash' not in item
    assert clients['s1'].get('/api/suggestions/public').json() == []
    with app.state.SessionLocal() as db:
        saved = db.scalar(select(Suggestion).where(Suggestion.id == item['id']))
        assert saved.receipt_hash == hashlib.sha256(token.encode()).hexdigest()
        assert saved.receipt_hash != token
    assert guest.post('/api/suggestions/receipt', json={'token': 'a' * 43}).status_code == 404
    assert guest.post('/api/suggestions/receipt', json={'token': item['id']}).status_code == 422
    assert clients['prof'].post(f"/api/suggestions/{item['id']}/replies", json={'content': '답변입니다'}).status_code == 201
    assert guest.post('/api/suggestions/receipt', json={'token': token}).json()['replies'][0]['content'] == '답변입니다'
    assert clients['prof'].post(f"/api/suggestions/{item['id']}/trash").status_code == 204
    assert guest.post('/api/suggestions/receipt', json={'token': token}).status_code == 404
