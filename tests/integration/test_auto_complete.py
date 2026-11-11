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
    for slot, student in zip(slots, ["s1", "s2", "s3"]):
        response = clients[student].post("/api/bookings", json={"slot_id": slot})
        assert response.status_code == 201
        ids.append(response.json()["id"])
    start = utcnow() - timedelta(minutes=15)
    now = utcnow()
    with factory.begin() as db:
        for sid, end in zip(slots, [start, now, now + timedelta(seconds=1), now, now]):
            slot = db.get(Slot, sid)
            slot.start_at, slot.end_at = end - timedelta(minutes=30), end
    assert complete_elapsed(factory, start, now) == 1
    assert complete_elapsed(factory, now, now) == 0
    assert complete_elapsed(factory, now + timedelta(hours=1), now + timedelta(hours=1)) == 1
    with factory() as db:
        assert [db.get(Booking, bid).status for bid in ids] == ["booked", "completed", "completed"]
        assert db.get(Booking, cancelled).status == "cancelled"
        logs = db.scalars(select(AuditLog).where(AuditLog.action == "booking.auto_completed")).all()
        assert sorted(log.target_id for log in logs) == sorted(str(bid) for bid in ids[1:])
        assert all(log.actor_id is None for log in logs)
    assert prof.post(f"/api/bookings/{ids[1]}/outcome", json={"outcome": "no_show"}).status_code == 200
    assert complete_elapsed(factory, start, now + timedelta(days=1)) == 0
