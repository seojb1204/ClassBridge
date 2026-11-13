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


def test_lecture_blocks_booking_preserves_slot(clients):
    p, s = clients["prof"], clients["s1"]
    ids = make_slots(p)
    assert p.post("/api/lectures", json=body()).status_code == 201
    listed = s.get("/api/slots", params={"start": future_day().isoformat()}).json()
    assert all(not x["bookable"] and x["reason"] == "강의 시간" for x in listed)
    r = s.post("/api/bookings", json={"slot_id": ids[0]})
    assert r.status_code == 409, r.text


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
