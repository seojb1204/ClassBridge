"""Exact clock boundaries for old-slot cancellation and new-slot booking policy."""
from datetime import timedelta

import pytest

from app.core.errors import Conflict
from app.db import utcnow
from app.models import Slot, User
from app.services import booking_service
from tests.conftest import make_slots


@pytest.mark.parametrize("old_seconds,new_seconds,allowed", [
    (1800, 3600, True), (1799, 3600, False),
    (3600, 1800, True), (3600, 1799, False),
])
def test_reschedule_checks_both_thirty_minute_boundaries(app, clients, old_seconds, new_seconds, allowed):
    slots = make_slots(clients["prof"])
    student = clients["s1"]
    bid = student.post("/api/bookings", json={"slot_id": slots[0]}).json()["id"]
    now = utcnow()
    with app.state.SessionLocal.begin() as db:
        for sid, seconds in zip(slots[:2], [old_seconds, new_seconds], strict=True):
            slot = db.get(Slot, sid)
            slot.start_at = now + timedelta(seconds=seconds)
            slot.end_at = slot.start_at + timedelta(minutes=20)
    with app.state.SessionLocal() as db:
        actor = db.get(User, student.me["id"])
        if allowed:
            assert booking_service.reschedule(db, actor, bid, slots[1], now=now).slot_id == slots[1]
        else:
            with pytest.raises(Conflict):
                booking_service.reschedule(db, actor, bid, slots[1], now=now)


def test_cancel_at_exact_thirty_minutes(app, clients):
    sid = make_slots(clients["prof"])[0]
    student = clients["s1"]
    bid = student.post("/api/bookings", json={"slot_id": sid}).json()["id"]
    now = utcnow()
    with app.state.SessionLocal.begin() as db:
        slot = db.get(Slot, sid)
        slot.start_at = now + timedelta(minutes=30)
        slot.end_at = now + timedelta(minutes=50)
    with app.state.SessionLocal() as db:
        actor = db.get(User, student.me["id"])
        assert booking_service.cancel(db, actor, bid, now=now).status == "cancelled"
