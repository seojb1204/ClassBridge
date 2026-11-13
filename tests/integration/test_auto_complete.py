from datetime import timedelta

from sqlalchemy import select

from app.db import utcnow
from app.models import AuditLog, Booking, Slot
from app.services.auto_complete import complete_elapsed
from tests.conftest import make_slots


def test_completion_boundaries_restart_and_manual_correction(app, clients):
    factory = app.state.SessionLocal
    prof = clients["prof"]
    slots = make_slots(prof, end="12:30")
    cancelled = clients["s3"].post("/api/bookings", json={"slot_id": slots[3]}).json()["id"]
    assert clients["s3"].post(f"/api/bookings/{cancelled}/cancel", json={}).status_code == 200
    ids = []
    for slot, student in zip(slots[:3], ["s1", "s2", "s3"], strict=True):
        response = clients[student].post("/api/bookings", json={"slot_id": slot})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    start = utcnow() - timedelta(minutes=15)
    now = utcnow()
    with factory.begin() as db:
        for sid, end in zip(slots, [start, now, now + timedelta(seconds=1), now, now], strict=True):
            slot = db.get(Slot, sid)
            slot.start_at, slot.end_at = end - timedelta(minutes=30), end
    assert complete_elapsed(factory, start, now) == 1
    assert complete_elapsed(factory, now, now) == 0
    assert complete_elapsed(factory, now + timedelta(hours=1), now + timedelta(hours=1)) == 1
    with factory() as db:
        assert [db.get(Booking, bid).status for bid in ids] == ["expired", "completed", "completed"]
        assert db.get(Booking, cancelled).status == "cancelled"
        logs = db.scalars(select(AuditLog).where(AuditLog.action == "booking.auto_completed")).all()
        assert sorted(log.target_id for log in logs) == sorted(str(bid) for bid in ids[1:])
        assert all(log.actor_id is None for log in logs)
    assert prof.post(f"/api/bookings/{ids[1]}/outcome", json={"outcome": "no_show"}).status_code == 200
    assert complete_elapsed(factory, start, now + timedelta(days=1)) == 0


def test_historical_expiry_preserves_history_and_allows_new_booking(app, clients):
    from app.models import BookingEvent
    factory = app.state.SessionLocal
    slots = make_slots(clients["prof"])
    student = clients["s1"]
    old_id = student.post("/api/bookings", json={"slot_id": slots[0]}).json()["id"]
    now = utcnow()
    with factory.begin() as db:
        slot = db.get(Slot, slots[0])
        slot.start_at, slot.end_at = now - timedelta(days=2), now - timedelta(days=2, minutes=-30)
        db.get(Booking, old_id).professor_note = "historical private note"
        events_before = list(db.scalars(select(BookingEvent.id).where(BookingEvent.booking_id == old_id)))
    assert complete_elapsed(factory, now - timedelta(days=1), now) == 0
    assert complete_elapsed(factory, now, now) == 0
    with factory() as db:
        old = db.get(Booking, old_id)
        assert old.status == "expired"
        assert old.professor_note == "historical private note"
        assert list(db.scalars(select(BookingEvent.id).where(BookingEvent.booking_id == old_id))) == events_before
        assert len(list(db.scalars(select(AuditLog).where(AuditLog.action == "booking.expired")))) == 1
    mine = student.get("/api/bookings/mine").json()
    assert next(b for b in mine if b["id"] == old_id)["status"] == "expired"
    assert "historical private note" not in str(mine)
    overview = clients["prof"].get("/api/staff/overview?days=7").json()
    assert overview["status_counts"]["expired"] == 1
    assert overview["completion_rate"] is None
    assert student.post("/api/bookings", json={"slot_id": slots[1]}).status_code == 201
    assert student.post(f"/api/bookings/{old_id}/outcome", json={"outcome": "completed"}).status_code == 403
    assert clients["prof"].post(f"/api/bookings/{old_id}/outcome", json={"outcome": "no_show"}).status_code == 200
    assert complete_elapsed(factory, now, now) == 0
    with factory() as db:
        assert db.get(Booking, old_id).status == "no_show"
