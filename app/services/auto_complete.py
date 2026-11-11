"""Complete elapsed consultations from this feature's first activation onward."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, update

from app.db import utcnow
from app.models import AppSetting, Booking, Slot
from app.repositories import audit

log = logging.getLogger("classbridge")
ACTIVATION_KEY = "booking_auto_complete_since"


def complete_elapsed(session_factory, started_at, now):
    with session_factory.begin() as db:
        marker = db.get(AppSetting, ACTIVATION_KEY)
        if marker is None:
            marker = AppSetting(key=ACTIVATION_KEY, value=started_at.isoformat())
            db.add(marker)
            db.flush()
        since = datetime.fromisoformat(marker.value)
        elapsed = select(Slot.id).where(Slot.status == "open", Slot.end_at > since, Slot.end_at <= now)
        ids = db.scalars(update(Booking).where(Booking.status == "booked", Booking.slot_id.in_(elapsed))
                         .values(status="completed").returning(Booking.id)).all()
        for booking_id in ids:
            audit.add(db, None, "booking.auto_completed", "booking", booking_id)
        return len(ids)


async def run(session_factory, stop):
    started_at = utcnow()
    while not stop.is_set():
        try:
            await asyncio.to_thread(complete_elapsed, session_factory, started_at, utcnow())
        except Exception as exc:
            log.error("automatic booking completion: %s", type(exc).__name__)
        try:
            await asyncio.wait_for(stop.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass
