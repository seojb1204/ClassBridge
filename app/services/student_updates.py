"""Owner-only projection. Never expose staff notes or general audit events."""
from sqlalchemy import select, update

from app.core.errors import NotFound
from app.models import Booking, BookingEvent

ACTIONS = ("book_by_staff", "cancel_by_staff", "cancel_by_slot", "rescheduled", "slot_changed")

def events(db, booking):
    return list(db.scalars(select(BookingEvent).where(
        BookingEvent.booking_id == booking.id, BookingEvent.action.in_(ACTIONS),
        BookingEvent.actor_id != booking.student_id).order_by(BookingEvent.id)))

def summary(db, booking):
    rows = events(db, booking)
    return {"latest_update_id": rows[-1].id if rows else 0,
            "unread_update": any(e.id > booking.student_seen_event_id for e in rows)}

def owned(db, student_id, booking_id):
    booking = db.scalar(select(Booking).where(Booking.id == booking_id, Booking.student_id == student_id))
    if booking is None:
        raise NotFound("예약을 찾을 수 없습니다")
    return booking

def detail(db, student_id, booking_id):
    booking = owned(db, student_id, booking_id)
    return [{"id": e.id, "action": e.action, "detail": e.detail, "at": e.at} for e in events(db, booking)]

def mark_read(db, student_id, booking_id, event_id):
    booking = owned(db, student_id, booking_id)
    # Acknowledge only the displayed event; later arrivals stay unread.
    if any(e.id == event_id for e in events(db, booking)):
        db.execute(update(Booking).where(Booking.id == booking_id,
            Booking.student_seen_event_id < event_id).values(student_seen_event_id=event_id))
        db.commit()
