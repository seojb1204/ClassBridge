"""상담 시간·예약 저장소. 정원 증감은 조건부 UPDATE로 원자적으로 처리한다."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from app.models import Blackout, Booking, BookingEvent, Slot, User


def get_slot(db: Session, slot_id: int, lock: bool = False) -> Slot | None:
    stmt = select(Slot).where(Slot.id == slot_id)
    if lock:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def list_slots(db: Session, start: datetime, end: datetime, include_cancelled: bool) -> list[Slot]:
    stmt = select(Slot).where(Slot.start_at >= start, Slot.start_at < end).order_by(Slot.start_at)
    if not include_cancelled:
        stmt = stmt.where(Slot.status == "open")
    return list(db.execute(stmt).scalars())


def overlapping_open_slots(db: Session, start: datetime, end: datetime, exclude_id: int | None = None) -> list[Slot]:
    stmt = select(Slot).where(Slot.status == "open", Slot.start_at < end, Slot.end_at > start)
    if exclude_id is not None:
        stmt = stmt.where(Slot.id != exclude_id)
    return list(db.execute(stmt).scalars())


def try_take_seat(db: Session, slot_id: int) -> bool:
    """정원이 남아 있을 때만 1석 차감. 동시 요청에서도 DB가 원자적으로 판단한다."""
    res = db.execute(
        update(Slot)
        .where(and_(Slot.id == slot_id, Slot.status == "open", Slot.booked_count < Slot.capacity))
        .values(booked_count=Slot.booked_count + 1)
        .execution_options(synchronize_session=False)
    )
    return res.rowcount == 1


def release_seat(db: Session, slot_id: int) -> None:
    db.execute(
        update(Slot).where(Slot.id == slot_id, Slot.booked_count > 0)
        .values(booked_count=Slot.booked_count - 1)
        .execution_options(synchronize_session=False)
    )


def get_booking(db: Session, booking_id: int, lock: bool = False) -> Booking | None:
    stmt = select(Booking).where(Booking.id == booking_id)
    if lock:
        stmt = stmt.with_for_update(of=Booking)
    return db.execute(stmt).unique().scalar_one_or_none()


def active_booking_of(db: Session, student_id: int) -> Booking | None:
    return db.execute(
        select(Booking).where(Booking.student_id == student_id, Booking.status == "booked")
    ).unique().scalar_one_or_none()


def bookings_of_student(db: Session, student_id: int) -> list[Booking]:
    return list(db.execute(
        select(Booking).where(Booking.student_id == student_id).order_by(Booking.created_at.desc())
    ).unique().scalars())


def active_bookings_for_slot(db: Session, slot_id: int) -> list[Booking]:
    return list(db.execute(
        select(Booking).where(Booking.slot_id == slot_id, Booking.status == "booked")
    ).unique().scalars())


def search_bookings(db: Session, start: datetime | None, end: datetime | None,
                    status: str | None) -> list[tuple[Booking, User]]:
    stmt = select(Booking, User).join(User, User.id == Booking.student_id).join(Slot, Slot.id == Booking.slot_id)
    if start:
        stmt = stmt.where(Slot.start_at >= start)
    if end:
        stmt = stmt.where(Slot.start_at < end)
    if status:
        stmt = stmt.where(Booking.status == status)
    stmt = stmt.order_by(Slot.start_at, Booking.id)
    return [(b, u) for b, u in db.execute(stmt).unique().all()]


def add_event(db: Session, booking_id: int, actor_id: int, action: str, detail: str = "") -> None:
    db.add(BookingEvent(booking_id=booking_id, actor_id=actor_id, action=action, detail=detail[:500]))


def events_for(db: Session, booking_id: int) -> list[BookingEvent]:
    return list(db.execute(
        select(BookingEvent).where(BookingEvent.booking_id == booking_id).order_by(BookingEvent.at, BookingEvent.id)
    ).scalars())


def blackout_days(db: Session, start: date | None = None, end: date | None = None) -> list[Blackout]:
    stmt = select(Blackout).order_by(Blackout.day)
    if start:
        stmt = stmt.where(Blackout.day >= start)
    if end:
        stmt = stmt.where(Blackout.day <= end)
    return list(db.execute(stmt).scalars())


def is_blackout(db: Session, day: date) -> bool:
    return db.execute(select(Blackout.id).where(Blackout.day == day)).first() is not None
