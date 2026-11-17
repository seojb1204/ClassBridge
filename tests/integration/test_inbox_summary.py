"""Staff-only notification summaries never pretend to be historical snapshots."""
from sqlalchemy import event, select

from app.models import InboxNotification, User
from app.models.booking import BookingEvent
from app.services.inbox import enqueue
from tests.conftest import login, make_slots


def create_booking(clients):
    sid = make_slots(clients['prof'])[0]
    response = clients['s1'].post('/api/bookings', json={
        'slot_id': sid, 'topic': 'private topic', 'applicant_name': '예약 이름',
        'student_number': 'PRIVATE-ID', 'grade': 1,
    })
    assert response.status_code == 201, response.text
    return response.json()['id']


def test_summary_minimal_authorized_current_data(app, clients):
    bid = create_booking(clients)
    item = clients['prof'].get('/api/inbox').json()['items'][0]
    summary = item['booking_summary']
    assert set(summary) == {'student_name', 'start_at', 'end_at', 'status', 'status_label', 'source'}
    assert summary['student_name'] == '예약 이름'
    assert summary['source'] == 'current' and summary['status_label'] == '예약됨'
    assert summary['start_at'].endswith('+09:00')
    assert item['body'].startswith('현재 예약 · ')
    assert all(secret not in str(item) for secret in ('PRIVATE-ID', 'private topic', 's1@test.ac.kr'))
    nid = item['id']
    assert clients['prof'].get(f'/api/inbox/{nid}/target').json()['notification'] == item
    assert clients['s1'].get('/api/inbox').status_code == 403
    assert clients['admin'].get(f'/api/inbox/{nid}/target').status_code == 404
    # Old "created" event is explicitly labeled as CURRENT info after cancellation.
    assert clients['prof'].post(f'/api/bookings/{bid}/cancel', json={'reason': 'private cancellation'}).status_code == 200
    old = next(x for x in clients['prof'].get('/api/inbox').json()['items'] if x['id'] == nid)
    assert old['kind'] == 'created'
    assert old['booking_summary']['status_label'] == '취소됨'
    assert old['body'].startswith('현재 예약 · ') and '→' not in old['body']
    assert 'private cancellation' not in str(old)
    with app.state.SessionLocal.begin() as db:
        db.get(User, clients['prof'].me['id']).role = 'student'
    assert clients['prof'].get('/api/inbox').status_code == 403
    assert clients['prof'].get(f'/api/inbox/{nid}/target').status_code == 403


def test_wrong_event_type_and_corrupt_keys_never_resolve(app, clients):
    bid = create_booking(clients)
    with app.state.SessionLocal.begin() as db:
        # A legacy/malformed notification must not link an unrelated note-update event.
        other = BookingEvent(booking_id=bid, actor_id=clients['prof'].me['id'], action='note_update')
        db.add(other)
        db.flush()
        keys = [f'booking-event-{other.id}', 'booking-event-99999999999999999999999999999999',
                'booking-event-0', 'booking-event-1trailing']
        for key in keys:
            enqueue(db, key, 'created')
    items = clients['prof'].get('/api/inbox').json()['items']
    assert len(items) == 5
    for item in items:
        if item['booking_summary']:
            continue
        assert item['body'] == '연결된 예약 정보를 확인할 수 없습니다.'
        target = clients['prof'].get(f"/api/inbox/{item['id']}/target").json()
        assert target['unavailable'] and target['booking'] is None


def test_summary_lookup_is_batched_and_account_scoped(app, clients):
    bid = create_booking(clients)
    with app.state.SessionLocal.begin() as db:
        for _ in range(20):
            ev = BookingEvent(booking_id=bid, actor_id=clients['prof'].me['id'], action='slot_changed')
            db.add(ev)
            db.flush()
            enqueue(db, f'booking-event-{ev.id}', 'slot_changed')
        db.get(User, clients['s2'].me['id']).role = 'professor'
    other = login(app, 's2@test.ac.kr')
    assert other.get('/api/inbox').json()['items'] == []
    statements = []

    def count_lookup(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'booking_events' in statement:
            statements.append(statement)

    event.listen(app.state.engine, 'before_cursor_execute', count_lookup)
    try:
        items = clients['prof'].get('/api/inbox').json()['items']
    finally:
        event.remove(app.state.engine, 'before_cursor_execute', count_lookup)
    assert len(items) == 21 and all(x['booking_summary'] for x in items)
    assert len(statements) == 1


def test_missing_deleted_event_no_false_booking(app, clients):
    create_booking(clients)
    with app.state.SessionLocal.begin() as db:
        notice = db.scalar(select(InboxNotification).where(
            InboxNotification.recipient_id == clients['prof'].me['id']))
        nid = notice.id
        linked = db.get(BookingEvent, int(notice.event_key.removeprefix('booking-event-')))
        db.delete(linked)
    target = clients['prof'].get(f'/api/inbox/{nid}/target').json()
    assert target['unavailable'] and target['booking'] is None
    assert target['notification']['booking_summary'] is None
    assert clients['prof'].get('/api/inbox').json()['items'][0]['booking_summary'] is None


def test_changed_summary_is_latest_not_invented_before_after(app, clients):
    bid = create_booking(clients)
    original = clients['prof'].get('/api/inbox').json()['items'][0]
    sid = make_slots(clients['prof'], start='14:00', end='15:00')[0]
    response = clients['prof'].post(f'/api/bookings/{bid}/reschedule', json={'new_slot_id': sid})
    assert response.status_code == 200, response.text
    items = clients['prof'].get('/api/inbox').json()['items']
    changed = next(i for i in items if i['kind'] == 'changed')
    prior = next(i for i in items if i['id'] == original['id'])
    for item in [changed, prior]:
        assert '14:00' in item['booking_summary']['start_at']
        assert item['booking_summary']['source'] == 'current'
        assert '현재 예약' in item['body'] and '→' not in item['body']
    assert clients['prof'].get(f"/api/inbox/{changed['id']}/target").json()['booking']['slot']['id'] == sid
