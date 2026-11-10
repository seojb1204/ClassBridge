"""Safe professor schedule previews and replacements."""
from __future__ import annotations

from sqlalchemy import select

from app.models import Booking, Slot
from tests.conftest import future_day, make_slots


def _spec(start="10:00", end="11:00", duration=60):
    return {"start_date": future_day().isoformat(), "start_time": start,
            "end_time": end, "duration_minutes": duration, "kind": "individual",
            "capacity": 1}


def test_preview_and_replace_only_unbooked_slots(app, clients):
    professor = clients["prof"]
    old = make_slots(professor, start="10:00", end="11:00", duration=30)
    body = _spec()
    preview = professor.post("/api/slots/preview", json=body)
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["created"] == 1 and p["replaced"] == 2
    assert sorted(p["overlap_ids"]) == sorted(old)
    assert p["protected_ids"] == []

    stale = professor.post("/api/slots/replace", json={**body, "expected_overlap_ids": [old[0]]})
    assert stale.status_code == 409 and stale.json()["error"] == "slot_preview_stale"

    result = professor.post("/api/slots/replace", json={**body, "expected_overlap_ids": p["overlap_ids"]})
    assert result.status_code == 200, result.text
    assert result.json()["created"] == 1 and result.json()["replaced"] == 2
    db = app.state.SessionLocal()
    try:
        assert all(db.get(Slot, sid).status == "cancelled" for sid in old)
        active = list(db.execute(select(Slot).where(Slot.status == "open")).scalars())
        assert len(active) == 1
        assert active[0].id in result.json()["slot_ids"]
    finally:
        db.close()


def test_replace_protects_any_booked_slot_and_preserves_booking(app, clients):
    professor, student = clients["prof"], clients["s1"]
    old = make_slots(professor, start="10:00", end="11:00", duration=30)
    booking = student.post("/api/bookings", json={"slot_id": old[0]})
    assert booking.status_code == 201, booking.text
    p = professor.post("/api/slots/preview", json=_spec()).json()
    assert p["protected_ids"] == [old[0]]
    res = professor.post("/api/slots/replace",
                         json={**_spec(), "expected_overlap_ids": p["overlap_ids"]})
    assert res.status_code == 409 and res.json()["error"] == "slot_has_bookings"
    db = app.state.SessionLocal()
    try:
        assert all(db.get(Slot, sid).status == "open" for sid in old)
        assert db.get(Booking, booking.json()["id"]).status == "booked"
        assert db.get(Slot, old[0]).booked_count == 1
    finally:
        db.close()


def test_student_cannot_preview_or_replace_slots(clients):
    student = clients["s1"]
    p = _spec()
    assert student.post("/api/slots/preview", json=p).status_code == 403
    assert student.post("/api/slots/replace", json={**p, "expected_overlap_ids": []}).status_code == 403


def test_policy_endpoint_reflects_admin_settings(clients):
    s, admin = clients["s1"], clients["admin"]
    initial = s.get("/api/booking-policy")
    assert initial.status_code == 200
    assert initial.json() == {
        "booking_window_days": 30, "booking_deadline_minutes": 30, "booking_deadline_hours": 0.5, "cancel_deadline_hours": 3
    }
    changed = admin.put("/api/admin/settings", json={"booking_deadline_hours": 5})
    assert changed.status_code == 200, changed.text
    assert s.get("/api/booking-policy").json()["booking_deadline_hours"] == 5
