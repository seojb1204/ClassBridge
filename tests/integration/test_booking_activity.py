from tests.conftest import make_slots


def test_student_cancellation_visible_to_both_staff_roles_only(clients):
    p, s = clients['prof'], clients['s1']
    slot = make_slots(p)[0]
    bid = s.post('/api/bookings', json={'slot_id': slot, 'applicant_name': '예약자',
                                      'topic': '노출하지 않는 상담 주제'}).json()['id']
    assert s.post(f'/api/bookings/{bid}/cancel', json={}).status_code == 200
    for role in ('prof', 'admin'):
        response = clients[role].get('/api/staff/booking-events?kind=cancel')
        assert response.status_code == 200
        item = response.json()['items'][0]
        assert item['booking_id'] == bid and item['action'] == 'cancel'
        assert item['actor_is_student'] is True and item['actor_name'] == '학생1'
        assert item['student_name'] == '예약자' and item['status'] == 'cancelled'
        assert item['at'] and item['start_at']
        assert 'topic' not in item and 'professor_note' not in item and 'student_email' not in item
    assert s.get('/api/staff/booking-events').status_code == 403
    assert clients['s2'].get('/api/staff/booking-events').status_code == 403
    assert s.post(f'/api/bookings/{bid}/cancel', json={}).status_code == 409
    assert len(p.get('/api/staff/booking-events?kind=cancel').json()['items']) == 1


def test_change_is_not_cancellation_and_cursor_is_stable(clients):
    p, s = clients['prof'], clients['s1']
    slots = make_slots(p)
    bid = s.post('/api/bookings', json={'slot_id': slots[0]}).json()['id']
    new = s.post(f'/api/bookings/{bid}/reschedule', json={'new_slot_id': slots[1]}).json()['id']
    assert p.get('/api/staff/booking-events?kind=cancel').json()['items'] == []
    changes = p.get('/api/staff/booking-events?kind=change').json()['items']
    assert {x['action'] for x in changes} == {'rescheduled_from', 'rescheduled_to'}
    first = p.get('/api/staff/booking-events?limit=1').json()
    assert p.post(f'/api/bookings/{new}/cancel', json={'reason': '운영 일정'}).status_code == 200
    second = p.get(f'/api/staff/booking-events?limit=1&before_id={first["next_before_id"]}').json()
    assert second['items'][0]['id'] < first['items'][0]['id']
    cancelled = p.get('/api/staff/booking-events?kind=cancel').json()['items'][0]
    assert cancelled['action'] == 'cancel_by_staff' and not cancelled['actor_is_student']
    assert p.get('/api/staff/booking-events?limit=101').status_code == 422
    assert p.get('/api/staff/booking-events?kind=unknown').status_code == 422


def test_slot_cancellation_is_included_and_failed_request_has_no_event(clients):
    p, s = clients['prof'], clients['s1']
    slot = make_slots(p)[0]
    bid = s.post('/api/bookings', json={'slot_id': slot}).json()['id']
    assert clients['s2'].post(f'/api/bookings/{bid}/cancel', json={}).status_code == 404
    assert p.get('/api/staff/booking-events?kind=cancel').json()['items'] == []
    assert p.post(f'/api/slots/{slot}/cancel', json={'force': True, 'reason': '상담 일정 취소'}).status_code == 200
    item = p.get('/api/staff/booking-events?kind=cancel').json()['items'][0]
    assert item['action'] == 'cancel_by_slot' and item['detail'] == '상담 일정 취소'
