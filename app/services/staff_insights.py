"""Read-only professor/admin insight queries.

Only aggregate counts and consultations with existing notes are returned. Anonymous
survey answers/suggestions are never joined or queried from this module.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Booking, Slot, User
from app.services.booking_service import kst_range
from app.timeutil import today_kst


def overview(db: Session, days: int) -> dict:
    today = today_kst(utcnow())
    start_day = today - timedelta(days=days - 1)
    start_at, end_at = kst_range(start_day, days)
    scoped = (Slot.start_at >= start_at, Slot.start_at < end_at)

    status_rows = db.execute(
        select(Booking.status, func.count(Booking.id))
        .join(Slot, Slot.id == Booking.slot_id)
        .where(*scoped)
        .group_by(Booking.status)
    ).all()
    statuses = {key: 0 for key in ("booked", "completed", "no_show", "cancelled", "expired")}
    statuses.update({status: count for status, count in status_rows})

    type_rows = db.execute(
        select(Booking.consultation_type, func.count(Booking.id))
        .join(Slot, Slot.id == Booking.slot_id)
        .where(*scoped)
        .group_by(Booking.consultation_type)
    ).all()
    mode_rows = db.execute(
        select(Booking.consultation_mode, func.count(Booking.id))
        .join(Slot, Slot.id == Booking.slot_id)
        .where(*scoped)
        .group_by(Booking.consultation_mode)
    ).all()
    recorded_notes = db.execute(
        select(func.count(Booking.id))
        .join(Slot, Slot.id == Booking.slot_id)
        .where(*scoped, func.length(func.trim(Booking.professor_note)) > 0)
    ).scalar_one()
    open_slots = db.execute(
        select(func.count(Slot.id)).where(*scoped, Slot.status == "open")
    ).scalar_one()

    next_start, next_end = kst_range(today, 14)
    upcoming = db.execute(
        select(func.count(Booking.id))
        .join(Slot, Slot.id == Booking.slot_id)
        .where(Booking.status == "booked", Slot.start_at >= utcnow(),
               Slot.start_at < next_end, Slot.start_at >= next_start)
    ).scalar_one()

    decided = statuses["completed"] + statuses["no_show"]
    return {
        "period_start": start_day,
        "period_end": today,
        "days": days,
        "total_bookings": sum(statuses.values()),
        "status_counts": statuses,
        "recorded_notes": recorded_notes,
        "open_slots": open_slots,
        "upcoming_14_days": upcoming,
        # Only finalized completed/no-show appointments are in this denominator.
        "completion_rate": round(statuses["completed"] / decided * 100, 1) if decided else None,
        "type_counts": dict(type_rows),
        "mode_counts": dict(mode_rows),
    }


def _escaped_pattern(query: str) -> str:
    # Escape LIKE wildcard characters so search is literal, not pattern syntax.
    escaped = query.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def notes(db: Session, query: str, limit: int, offset: int) -> dict:
    criteria = [func.length(func.trim(Booking.professor_note)) > 0]
    if query.strip():
        pattern = _escaped_pattern(query)
        criteria.append(or_(
            func.lower(User.name).like(pattern, escape="\\"),
            func.lower(Booking.applicant_name).like(pattern, escape="\\"),
            func.lower(Booking.student_number).like(pattern, escape="\\"),
            func.lower(Booking.professor_note).like(pattern, escape="\\"),
        ))
    base = (select(Booking, User, Slot)
            .join(User, User.id == Booking.student_id)
            .join(Slot, Slot.id == Booking.slot_id)
            .where(*criteria))
    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    rows = db.execute(
        base.order_by(Slot.start_at.desc(), Booking.id.desc())
        .limit(limit).offset(offset)
    ).all()
    return {
        "total": total,
        "items": [
            {
                "booking_id": b.id,
                "start_at": slot.start_at,
                "student_name": b.applicant_name or user.name,
                "student_number": b.student_number,
                "consultation_type": b.consultation_type,
                "consultation_mode": b.consultation_mode,
                "status": b.status,
                "note": b.professor_note,
            }
            for b, user, slot in rows
        ],
    }
