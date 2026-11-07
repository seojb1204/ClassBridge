"""Staff-only projection of existing transactional booking events."""
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models import Booking, BookingEvent, User

CANCELLATIONS = ("cancel", "cancel_by_staff", "cancel_by_slot")
CHANGES = ("rescheduled_from", "rescheduled_to", "slot_changed")
ACTIONS = CANCELLATIONS + CHANGES + ("book", "book_by_staff", "completed", "no_show")


def list_activity(db: Session, kind: str, before_id: int | None, limit: int):
    student, actor = aliased(User), aliased(User)
    stmt = (select(BookingEvent, Booking, student.name, actor.name)
            .join(Booking, Booking.id == BookingEvent.booking_id)
            .join(student, student.id == Booking.student_id)
            .join(actor, actor.id == BookingEvent.actor_id)
            .where(BookingEvent.action.in_(CANCELLATIONS if kind == "cancel" else
                                          CHANGES if kind == "change" else ACTIONS)))
    if before_id is not None:
        stmt = stmt.where(BookingEvent.id < before_id)
    rows = db.execute(stmt.order_by(BookingEvent.id.desc()).limit(limit + 1)).all()
    items = [{"id": ev.id, "booking_id": b.id, "action": ev.action, "at": ev.at,
              "actor_name": actor_name, "actor_is_student": ev.actor_id == b.student_id,
              "student_name": b.applicant_name or student_name, "start_at": b.slot.start_at,
              "end_at": b.slot.end_at, "status": b.status, "detail": ev.detail}
             for ev, b, student_name, actor_name in rows[:limit]]
    return {"items": items, "next_before_id": items[-1]["id"] if len(rows) > limit else None}
