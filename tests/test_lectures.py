from tests.conftest import future_day, make_slots


def body(**kw):
    return dict(
        title="자료구조", location="101호", date=future_day().isoformat(), start_time="10:00", end_time="11:00", **kw
    )


def test_lecture_roles_and_weekly(clients):
    assert clients["s1"].get("/api/lectures", params={"start": future_day().isoformat()}).status_code == 403
    assert clients["s1"].post("/api/lectures", json=body()).status_code == 403
    r = clients["prof"].post("/api/lectures", json=body(weeks=3))
    assert r.status_code == 201, r.text
    assert len(r.json()) == 3
    assert len({x["series_id"] for x in r.json()}) == 1
    assert all(x["event_type"] == "lecture" and not x["bookable"] for x in r.json())


def test_registered_consultation_overrides_lecture(clients):
    p, s = clients["prof"], clients["s1"]
    ids = make_slots(p)
    assert p.post("/api/lectures", json=body()).status_code == 201
    listed = s.get("/api/slots", params={"start": future_day().isoformat()}).json()
    assert all(x["bookable"] and x["reason"] == "" for x in listed)
    days = s.get("/api/slots/available-days").json()
    assert any(d["date"] == future_day().isoformat() for d in days)
    r = s.post("/api/bookings", json={"slot_id": ids[0]})
    assert r.status_code == 201, r.text
    moved = s.post(f"/api/bookings/{r.json()['id']}/reschedule", json={"new_slot_id": ids[1]})
    assert moved.status_code == 200, moved.text


def test_existing_booking_prevents_lecture(clients):
    p, s = clients["prof"], clients["s1"]
    ids = make_slots(p)
    booking = s.post("/api/bookings", json={"slot_id": ids[0]})
    assert booking.status_code == 201, booking.text
    assert p.post("/api/lectures", json=body()).status_code == 409
    assert p.get("/api/lectures", params={"start": future_day().isoformat()}).json() == []


def test_boundary_and_soft_cancel(clients):
    p = clients["prof"]
    first = p.post("/api/lectures", json=body()).json()
    second = body()
    second.update(start_time="11:00", end_time="12:00")
    assert p.post("/api/lectures", json=second).status_code == 201
    assert p.post("/api/lectures", json=body()).status_code == 409
    assert p.post(f"/api/lectures/{first[0]['id']}/cancel").status_code == 200
    assert p.post("/api/lectures", json=body()).status_code == 201


def test_invalid_time_and_title(clients):
    p = clients["prof"]
    for changes in ({"title": " "}, {"weeks": 27}, {"end_time": "09:00"}, {"start_time": "10:01:01"}):
        value = body()
        value.update(changes)
        assert p.post("/api/lectures", json=value).status_code == 422
    value = body()
    value.update(start_time="19:00", end_time="21:00")
    assert p.post("/api/lectures", json=value).status_code == 201


def test_priority_preserves_capacity_and_staff_booking(clients):
    p, s1, s2 = clients['prof'], clients['s1'], clients['s2']
    ids = make_slots(p)
    assert p.post('/api/lectures', json=body()).status_code == 201
    student_id = s1.get('/api/me').json()['id']
    r = p.post('/api/bookings', json={'slot_id': ids[0], 'student_id': student_id})
    assert r.status_code == 201, r.text
    assert s2.post('/api/bookings', json={'slot_id': ids[0]}).status_code == 409
    listed = s2.get('/api/slots', params={'start': future_day().isoformat()}).json()
    full = next(x for x in listed if x['id'] == ids[0])
    assert not full['bookable'] and full['reason'] == '마감'
