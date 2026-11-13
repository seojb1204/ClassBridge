"""In-place schedule edits preserve identity, history, capacity, and outbox atomicity."""
import pytest
from sqlalchemy import func, select

from app.db import utcnow
from app.models import Booking, BookingEvent, Notification, Slot, User
from app.services import booking_service
from tests.conftest import make_slots
from tests.integration.test_notifications import enable, rows


def test_move_keeps_identity_metadata_notes_and_single_change_notice(app, clients):
    enable(app)
    slots = make_slots(clients["prof"])
    student = clients["s1"]
    old = student.post("/api/bookings", json={"slot_id": slots[0], "topic": "fixture topic"}).json()
    with app.state.SessionLocal.begin() as db:
        booking = db.get(Booking, old["id"])
        booking.professor_note = "synthetic private note"
        created_at, creator = booking.created_at, booking.created_by_id
        original_event = db.scalar(select(BookingEvent.id).where(BookingEvent.booking_id == booking.id))
        before_start = db.get(Slot, slots[0]).start_at.isoformat()
        db.get(Slot, slots[0]).location = "old location"
        db.get(Slot, slots[1]).location = "new location"
    response = student.post(f"/api/bookings/{old['id']}/reschedule", json={
        "new_slot_id": slots[1], "expected_slot_id": slots[0]})
    assert response.status_code == 200, response.text
    assert response.json()["id"] == old["id"]
    assert response.json()["status"] == "booked"
    assert response.json()["slot"]["id"] == slots[1]
    assert "synthetic private note" not in response.text
    with app.state.SessionLocal() as db:
        booking = db.get(Booking, old["id"])
        assert booking.created_at == created_at and booking.created_by_id == creator
        assert booking.professor_note == "synthetic private note" and booking.topic == "fixture topic"
        assert db.scalar(select(func.count()).select_from(Booking)) == 1
        assert db.get(BookingEvent, original_event).action == "book"
        event = db.scalar(select(BookingEvent).where(BookingEvent.action == "rescheduled"))
        assert event.booking_id == old["id"]
        assert before_start in event.detail and "old location" in event.detail and "new location" in event.detail
        assert db.get(Slot, slots[0]).booked_count == 0
        assert db.get(Slot, slots[1]).booked_count == 1
    queue = rows(app)
    assert [r.payload["kind"] for r in queue] == ["created", "changed"]
    assert queue[1].booking_id == queue[0].booking_id == old["id"]
    assert queue[1].chain_id == queue[0].chain_id
    assert queue[1].payload["old_start"] == before_start
    assert queue[1].payload["start"] != before_start
    assert "private" not in str(queue[1].payload)


def test_stale_move_rejected_without_second_transfer(app, clients):
    slots = make_slots(clients["prof"], end="11:30")
    student = clients["s1"]
    bid = student.post("/api/bookings", json={"slot_id": slots[0]}).json()["id"]
    url = f"/api/bookings/{bid}/reschedule"
    assert student.post(url, json={"new_slot_id": slots[1], "expected_slot_id": slots[0]}).status_code == 200
    stale = student.post(url, json={"new_slot_id": slots[2], "expected_slot_id": slots[0]})
    assert stale.status_code == 409 and stale.json()["error"] == "booking_changed"
    with app.state.SessionLocal() as db:
        assert db.get(Booking, bid).slot_id == slots[1]
        assert [db.get(Slot, sid).booked_count for sid in slots] == [0, 1, 0]
        assert db.scalar(select(func.count()).select_from(BookingEvent).where(BookingEvent.action == "rescheduled")) == 1


def test_failure_after_move_rolls_back_identity_history_and_seats(app, clients, monkeypatch):
    enable(app)
    slots = make_slots(clients["prof"])
    student = clients["s1"]
    bid = student.post("/api/bookings", json={"slot_id": slots[0]}).json()["id"]
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic outbox failure")
    monkeypatch.setattr(booking_service, "enqueue", fail)
    with app.state.SessionLocal() as db:
        actor = db.get(User, student.me["id"])
        with pytest.raises(RuntimeError, match="synthetic"):
            booking_service.reschedule(db, actor, bid, slots[1], now=utcnow())
    with app.state.SessionLocal() as db:
        assert db.get(Booking, bid).slot_id == slots[0]
        assert db.get(Booking, bid).status == "booked"
        assert [db.get(Slot, sid).booked_count for sid in slots] == [1, 0]
        assert db.scalar(select(func.count()).select_from(BookingEvent)) == 1
        assert db.scalar(select(func.count()).select_from(Notification)) == 1
