"""A rescheduling horizon differs from the new-booking horizon."""
from datetime import timedelta

from tests.conftest import future_day, make_slots


def test_far_future_visible_for_rescheduling_only(clients):
    prof, student, other = clients["prof"], clients["s1"], clients["s2"]
    near = make_slots(prof)[0]
    far_day = future_day() + timedelta(days=90)
    far = make_slots(prof, day=far_day)[0]
    assert student.post("/api/bookings", json={"slot_id": near}).status_code == 201
    url = f"/api/slots?start={far_day.isoformat()}&days=1"
    view = next(s for s in student.get(url).json() if s["id"] == far)
    assert view["bookable"] is True
    assert not next(s for s in other.get(url).json() if s["id"] == far)["bookable"]
    available = student.get("/api/slots/available-days").json()
    assert any(d["date"] == far_day.isoformat() and d["count"] > 0 for d in available)
    assert not any(d["date"] == far_day.isoformat() for d in other.get("/api/slots/available-days").json())
    assert other.post("/api/bookings", json={"slot_id": far}).json()["error"] == "booking_window"


def test_available_days_requires_login(app):
    from fastapi.testclient import TestClient
    assert TestClient(app).get("/api/slots/available-days").status_code == 401


def test_far_future_change_keeps_booking_id(clients):
    prof, student = clients["prof"], clients["s1"]
    near = make_slots(prof)[0]
    far = make_slots(prof, day=future_day() + timedelta(days=90))[0]
    bid = student.post("/api/bookings", json={"slot_id": near}).json()["id"]
    changed = student.post(f"/api/bookings/{bid}/reschedule", json={"new_slot_id": far, "expected_slot_id": near})
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] == bid and changed.json()["slot"]["id"] == far
