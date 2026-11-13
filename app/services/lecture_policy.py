"""Global single-professor calendar exclusion; shared transaction lock on PostgreSQL."""

from sqlalchemy import select, text

from app.core.errors import Conflict
from app.models import Booking, Lecture, Slot


def lock_calendar(db):
    # Acquire before booking/slot row locks in every writer to avoid lock inversion.
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(168482, 1)"))


def lecture_overlap(db, start, end, exclude_id=None):
    query = select(Lecture.id).where(Lecture.status == "active", Lecture.start_at < end, Lecture.end_at > start)
    if exclude_id is not None:
        query = query.where(Lecture.id != exclude_id)
    return db.scalar(query.limit(1)) is not None


def ensure_lecture_allowed(db, start, end, exclude_id=None):
    if lecture_overlap(db, start, end, exclude_id):
        raise Conflict("이미 등록된 강의와 시간이 겹칩니다", code="lecture_overlap")
    booking = db.scalar(
        select(Booking.id)
        .join(Slot, Slot.id == Booking.slot_id)
        .where(Booking.status == "booked", Slot.start_at < end, Slot.end_at > start)
        .limit(1)
    )
    if booking is not None:
        raise Conflict(
            "기존 상담 예약과 겹쳐 강의를 저장할 수 없습니다. 기존 예약은 유지됩니다.", code="lecture_booking_overlap"
        )
