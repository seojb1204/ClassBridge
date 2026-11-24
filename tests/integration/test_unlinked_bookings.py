"""Optional student linkage must preserve capacity, privacy and atomic writes."""
import pytest
from sqlalchemy import func, select

from app.models import Booking, Slot
from tests.conftest import future_day, make_slots


def payload(**kw):
    day = future_day().isoformat()
    return dict(applicant_name="계정 없는 학생", start_at=f"{day}T14:00:00+09:00",
                end_at=f"{day}T14:30:00+09:00", location="상담실", **kw)


@pytest.mark.parametrize("role", ["prof", "admin"])
def test_named_booking_without_account_is_private_and_manageable(app, clients, role):
    staff, student = clients[role], clients["s1"]
    response = staff.post("/api/bookings", json=payload())
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["student_id"] is None and booking["student_name"] == "계정 없는 학생"
    bid = booking["id"]
    assert student.get("/api/bookings/mine").json() == []
    assert student.get("/api/bookings").status_code == 403
    assert student.post(f"/api/bookings/{bid}/cancel", json={}).status_code in (403, 404)
    assert student.get(f"/api/bookings/{bid}/updates").status_code in (403, 404)
    assert staff.get("/api/bookings").json()[0]["id"] == bid
    assert staff.put(f"/api/bookings/{bid}/note", json={"note": "기록 보존"}).status_code == 200
    notes = staff.get("/api/staff/notes?q=계정 없는 학생")
    assert notes.status_code == 200 and "계정 없는 학생" in notes.text
    activity = staff.get("/api/staff/booking-events")
    assert activity.status_code == 200 and "계정 없는 학생" in activity.text
    inbox = staff.get("/api/inbox")
    assert inbox.status_code == 200 and "계정 없는 학생" in inbox.text
    day = future_day().isoformat()
    export = staff.get(f"/api/exports/consultations?start={day}&end={day}&format=csv&include_contacts=true")
    assert export.status_code == 200 and "계정 없는 학생" in export.text
    target = make_slots(staff, start="15:00", end="15:30")[0]
    moved = staff.post(f"/api/bookings/{bid}/reschedule", json={"new_slot_id": target})
    assert moved.status_code == 200, moved.text
    assert moved.json()["student_id"] is None
    assert staff.post(f"/api/bookings/{bid}/cancel", json={"reason": "일정 변경"}).status_code == 200
    with app.state.SessionLocal() as db:
        assert db.get(Slot, target).booked_count == 0


def test_optional_linkage_retains_students_own_reservation(clients):
    staff, student = clients["prof"], clients["s1"]
    response = staff.post("/api/bookings", json=payload(student_id=student.me["id"]))
    assert response.status_code == 201, response.text
    assert student.get("/api/bookings/mine").json()[0]["id"] == response.json()["id"]
    assert clients["s2"].get("/api/bookings/mine").json() == []


def test_unlinked_validation_and_capacity_preserve_slots(app, clients):
    staff = clients["prof"]
    assert staff.post("/api/bookings", json={**payload(), "applicant_name": "  "}).status_code == 400
    assert clients["s1"].post("/api/bookings", json=payload()).status_code == 403
    assert staff.post("/api/bookings", json={**payload(), "end_at": payload()["start_at"]}).status_code == 400
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Slot)) == 0
    first = staff.post("/api/bookings", json=payload())
    assert first.status_code == 201
    repeat = staff.post("/api/bookings", json=payload())
    assert repeat.status_code == 409 and repeat.json()["error"] == "slot_full"
    overlap = staff.post("/api/bookings", json={**payload(), "end_at": f"{future_day()}T15:00:00+09:00"})
    assert overlap.status_code == 409 and overlap.json()["error"] == "slot_overlap"
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Slot)) == 1
        assert db.scalar(select(func.count()).select_from(Booking)) == 1
    # A second unlinked person at another time is allowed (no shared dummy account).
    second = staff.post("/api/bookings", json={**payload(), "start_at": f"{future_day()}T15:00:00+09:00",
                                              "end_at": f"{future_day()}T15:30:00+09:00"})
    assert second.status_code == 201, second.text


def test_failed_outbox_rolls_back_new_slot_and_booking(app, clients, monkeypatch):
    from app.services import booking_service
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic outbox failure")
    monkeypatch.setattr(booking_service, "enqueue", fail)
    with pytest.raises(RuntimeError, match="synthetic"):
        clients["prof"].post("/api/bookings", json=payload())
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Slot)) == 0
        assert db.scalar(select(func.count()).select_from(Booking)) == 0


def test_lecture_conflict_and_existing_consultation_priority(app, clients):
    staff = clients["prof"]
    day = future_day().isoformat()
    assert staff.post("/api/lectures", json={"title": "강의", "date": day,
                     "start_time": "14:00", "end_time": "15:00"}).status_code == 201
    rejected = staff.post("/api/bookings", json=payload())
    assert rejected.status_code == 409 and rejected.json()["error"] == "lecture_overlap"
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Slot)) == 0
    # Explicitly registered consultation takes precedence over a lecture (existing policy).
    slot = make_slots(staff, start="14:00", end="14:30", location="상담실")[0]
    accepted = staff.post("/api/bookings", json=payload())
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["slot"]["id"] == slot
