from datetime import datetime

from app.models import Booking, Slot
from tests.conftest import future_day, make_slots
from tests.test_lectures import body


def test_recurrence_conflict_rolls_back_all_occurrences(clients):
    p = clients['prof']
    later = body()
    later['date'] = future_day(9).isoformat()
    assert p.post('/api/lectures', json=later).status_code == 201
    assert p.post('/api/lectures', json=body(weeks=3)).status_code == 409
    rows = p.get('/api/lectures', params={'start': future_day().isoformat(), 'days': 30}).json()
    assert len(rows) == 1


def test_failed_reschedule_preserves_booking_and_counts(clients, app):
    p, s = clients['prof'], clients['s1']
    old = make_slots(p, start='09:00', end='09:30')[0]
    target = make_slots(p)[0]
    b = s.post('/api/bookings', json={'slot_id': old}).json()
    assert p.post('/api/lectures', json=body()).status_code == 201
    response = s.post(f"/api/bookings/{b['id']}/reschedule", json={'new_slot_id': target})
    assert response.status_code == 409, response.text
    with app.state.SessionLocal() as db:
        saved = db.get(Booking, b['id'])
        assert saved.slot_id == old and saved.status == 'booked'
        assert db.get(Slot, old).booked_count == 1
        assert db.get(Slot, target).booked_count == 0


def test_student_cannot_change_or_cancel_lecture(clients):
    p, s = clients['prof'], clients['s1']
    identifier = p.post('/api/lectures', json=body()).json()[0]['id']
    assert s.patch(f'/api/lectures/{identifier}', json=body()).status_code == 403
    assert s.post(f'/api/lectures/{identifier}/cancel?series=true').status_code == 403
    assert len(p.get('/api/lectures', params={'start': future_day().isoformat()}).json()) == 1


def test_staff_proxy_booking_cannot_bypass_lecture(clients):
    p, s = clients['prof'], clients['s1']
    slot = make_slots(p)[0]
    assert p.post('/api/lectures', json=body()).status_code == 201
    response = p.post('/api/bookings', json={'slot_id': slot, 'student_id': s.me['id']})
    assert response.status_code == 409, response.text


def test_lecture_update_into_booked_slot_preserves_both(clients, app):
    p, s = clients['prof'], clients['s1']
    slot = make_slots(p, start='12:00', end='12:30')[0]
    booking = s.post('/api/bookings', json={'slot_id': slot}).json()
    lecture = p.post('/api/lectures', json=body()).json()[0]
    changed = body()
    changed.update(start_time='12:00', end_time='13:00')
    assert p.patch(f"/api/lectures/{lecture['id']}", json=changed).status_code == 409
    rows = p.get('/api/lectures', params={'start': future_day().isoformat()}).json()
    assert datetime.fromisoformat(rows[0]['start_at']) == datetime.fromisoformat(lecture['start_at'])
    with app.state.SessionLocal() as db:
        assert db.get(Booking, booking['id']).status == 'booked'
        assert db.get(Slot, slot).booked_count == 1
