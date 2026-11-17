from datetime import datetime, timedelta

import pytest

from app.core.errors import Conflict
from app.services.calendar_policy import ensure_weekday, touches_weekend
from tests.conftest import future_day, make_slots


def next_day(weekday):
    day = future_day(3)
    return day + timedelta(days=(weekday - day.weekday()) % 7)


@pytest.mark.parametrize('start,end,blocked', [
    ('2026-11-20T14:00:00Z', '2026-11-20T15:00:00Z', False),
    ('2026-11-20T14:00:00Z', '2026-11-20T15:01:00Z', True),
    ('2026-11-20T16:00:00Z', '2026-11-20T17:00:00Z', True),
    ('2026-11-22T15:00:00Z', '2026-11-22T16:00:00Z', False),
    ('2026-11-20T12:00:00Z', '2026-11-23T03:00:00Z', True),
])
def test_kst_whole_interval(start, end, blocked):
    a, b = datetime.fromisoformat(start), datetime.fromisoformat(end)
    assert touches_weekend(a, b) is blocked
    assert touches_weekend(a.replace(tzinfo=None), b.replace(tzinfo=None)) is blocked
    if blocked:
        with pytest.raises(Conflict, match='주말'):
            ensure_weekday(a, b)
    else:
        ensure_weekday(a, b)


def test_weekend_slot_create_preview_replace_rejected_atomically(clients):
    prof = clients['prof']
    body = dict(start_date=next_day(0).isoformat(), start_time='10:00', end_time='11:00',
                duration_minutes=30, weekdays=[0, 5], repeat_weeks=2)
    for route in ['/api/slots', '/api/slots/preview', '/api/slots/replace']:
        value = dict(body)
        if route.endswith('replace'):
            value['expected_overlap_ids'] = []
        response = prof.post(route, json=value)
        assert response.status_code == 409, response.text
        assert response.json()['error'] == 'weekend_unavailable'
    assert prof.get('/api/slots', params={'start':next_day(0).isoformat(), 'days':21}).json() == []


def test_weekday_create_and_weekend_move_blocked(clients):
    prof = clients['prof']
    slot = make_slots(prof, day=next_day(0))[0]
    saturday = next_day(5).isoformat()
    response = prof.patch(f'/api/slots/{slot}', json={
        'start_at':f'{saturday}T10:00:00+09:00', 'end_at':f'{saturday}T11:00:00+09:00'})
    assert response.status_code == 409, response.text
    lecture = {'title':'강의', 'date':next_day(0).isoformat(), 'start_time':'13:00', 'end_time':'14:00'}
    created = prof.post('/api/lectures', json=lecture)
    assert created.status_code == 201, created.text
    lecture.update(date=saturday, weeks=3)
    assert prof.post('/api/lectures', json=lecture).status_code == 409
    lecture['weeks'] = 1
    assert prof.patch(f'/api/lectures/{created.json()[0]["id"]}', json=lecture).status_code == 409
    assert clients['s1'].post('/api/lectures', json=lecture).status_code == 403


def test_legacy_weekend_query_cancel_and_new_bookings_blocked(app, clients):
    from app.models import Booking, Lecture, Slot
    prof, student = clients['prof'], clients['s1']
    saturday = next_day(5)
    start = datetime.fromisoformat(f'{saturday}T10:00:00+09:00')
    with app.state.SessionLocal.begin() as db:
        slot = Slot(start_at=start, end_at=start + timedelta(hours=1), created_by_id=prof.me['id'], booked_count=1)
        empty = Slot(start_at=start + timedelta(hours=2), end_at=start + timedelta(hours=3),
                     created_by_id=prof.me['id'])
        lecture = Lecture(title='기존 주말 강의', start_at=start + timedelta(hours=4),
                          end_at=start + timedelta(hours=5), created_by_id=prof.me['id'], series_id='legacy-weekend')
        db.add_all([slot, empty, lecture])
        db.flush()
        booking = Booking(slot_id=slot.id, student_id=student.me['id'], created_by_id=student.me['id'])
        db.add(booking)
        db.flush()
        slot_id, empty_id, booking_id, lecture_id = slot.id, empty.id, booking.id, lecture.id
    listed = student.get('/api/slots', params={'start':saturday.isoformat()}).json()
    assert all(not row['bookable'] for row in listed)
    assert next(row for row in listed if row['id'] == empty_id)['reason'] == '주말 예약 불가'
    for client in [student, clients['s2'], prof]:
        available = client.get('/api/slots/available-days').json()
        assert saturday.isoformat() not in [row['date'] for row in available]
    assert student.get('/api/bookings/mine').json()[0]['id'] == booking_id
    assert clients['s2'].post('/api/bookings', json={'slot_id':empty_id}).status_code == 409
    assert prof.post('/api/bookings', json={'slot_id':empty_id, 'student_id':clients['s2'].me['id']}).status_code == 409
    assert student.post(f'/api/bookings/{booking_id}/reschedule', json={'new_slot_id':empty_id}).status_code == 409
    assert student.get('/api/bookings/mine').json()[0]['slot']['id'] == slot_id
    assert clients['s2'].post(f'/api/bookings/{booking_id}/cancel', json={}).status_code == 404
    weekday = make_slots(prof, day=next_day(0))[0]
    assert prof.post(f'/api/bookings/{booking_id}/reschedule', json={'new_slot_id':weekday}).status_code == 200
    assert student.post(f'/api/bookings/{booking_id}/cancel', json={}).status_code == 200
    lectures = prof.get('/api/lectures', params={'start':saturday.isoformat()}).json()
    assert lectures[0]['id'] == lecture_id
    assert prof.post(f'/api/lectures/{lecture_id}/cancel').status_code == 200
    with app.state.SessionLocal() as db:
        assert db.get(Slot, slot_id) is not None
        assert db.get(Lecture, lecture_id).status == 'cancelled'
