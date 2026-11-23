"""Retention report is read-only and counts only records past 365 days."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from app.db import utcnow
from app.models import Booking, Slot, Suggestion
from app.services.retention import overdue
from tests.conftest import make_slots


def test_reports_overdue_records_without_changing_anything(app, clients):
    prof, s1 = clients["prof"], clients["s1"]
    old_slot, new_slot = make_slots(prof)
    assert s1.post("/api/bookings", json={"slot_id": old_slot}).status_code == 201
    assert clients["s2"].post("/api/bookings", json={"slot_id": new_slot}).status_code == 201
    now = utcnow()
    with app.state.SessionLocal() as db:
        slot = db.get(Slot, old_slot)
        slot.start_at = now - timedelta(days=400)
        slot.end_at = slot.start_at + timedelta(minutes=30)
        db.add(Suggestion(id="00000000-0000-4000-8000-000000000001", category="other", content="오래된 건의",
                          submitted_on=(now - timedelta(days=500)).date()))
        db.add(Suggestion(id="00000000-0000-4000-8000-000000000002", category="other", content="최근 건의",
                          submitted_on=now.date()))
        db.commit()
    with app.state.SessionLocal() as db:
        before = (db.scalar(select(func.count(Booking.id))), db.scalar(select(func.count(Suggestion.id))))
        report = overdue(db, now)
        db.rollback()
        after = (db.scalar(select(func.count(Booking.id))), db.scalar(select(func.count(Suggestion.id))))
    assert report["bookings"]["count"] == 1
    assert report["suggestions"]["count"] == 1
    assert report["surveys"]["count"] == 0 and report["support_tickets"]["count"] == 0
    assert before == after
    text = str(report)
    assert "오래된 건의" not in text and "@" not in text
