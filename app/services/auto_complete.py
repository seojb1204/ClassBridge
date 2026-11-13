"""Complete elapsed consultations from this feature's first activation onward."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import func, select, update

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
        # Preserve historical uncertainty: elapsed pre-activation bookings are
        # inactive, but must never be asserted to have been attended or missed.
        historical = select(Slot.id).where(Slot.status == "open", Slot.end_at <= since, Slot.end_at <= now)
        expired = db.scalars(update(Booking).where(Booking.status == "booked", Booking.slot_id.in_(historical))
                            .values(status="expired").returning(Booking.id)).all()
        for booking_id in expired:
            audit.add(db, None, "booking.expired", "booking", booking_id)
        elapsed = select(Slot.id).where(Slot.status == "open", Slot.end_at > since, Slot.end_at <= now)
        ids = db.scalars(update(Booking).where(Booking.status == "booked", Booking.slot_id.in_(elapsed))
                         .values(status="completed").returning(Booking.id)).all()
        for booking_id in ids:
            audit.add(db, None, "booking.auto_completed", "booking", booking_id)
        return len(ids)


def next_delay(session_factory, now):
    """Sleep until a real booking ends, not every 30 seconds when idle.

    Foreground writes wake the worker; six-hour reconciliation covers external
    edits in the documented single-instance deployment.
    """
    with session_factory() as db:
        due = db.scalar(select(func.min(Slot.end_at)).join(Booking, Booking.slot_id == Slot.id)
                        .where(Slot.status == "open", Booking.status == "booked", Slot.end_at > now))
    return min(21600, max(0.1, (due - now).total_seconds())) if due else 21600


async def run(session_factory, stop, wake=None):
    wake = wake or asyncio.Event()
    started_at = utcnow()
    while not stop.is_set():
        wake.clear()
        delay = 30  # Preserve prompt recovery after transient DB failures.
        try:
            scanned_at = utcnow()
            await asyncio.to_thread(complete_elapsed, session_factory, started_at, scanned_at)
            delay = await asyncio.to_thread(next_delay, session_factory, scanned_at)
            delay = max(0, delay - (utcnow() - scanned_at).total_seconds())
        except Exception as exc:
            log.error("automatic booking completion: %s", type(exc).__name__)
        waits = [asyncio.create_task(stop.wait()), asyncio.create_task(wake.wait())]
        try:
            await asyncio.wait(waits, timeout=delay, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in waits:
                task.cancel()
            await asyncio.gather(*waits, return_exceptions=True)
