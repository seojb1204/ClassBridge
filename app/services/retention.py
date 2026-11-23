"""Read-only retention check against the published privacy policy (up to 365 days).

Lists how many records are past their retention limit so the operator can review
and delete them through the existing, confirmed delete paths. This module never
deletes or modifies data, and returns counts and identifiers only (no names,
e-mail addresses or free text).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, Slot, Suggestion
from app.models.support import SupportTicket
from app.models.survey import Survey
from app.timeutil import today_kst

RETENTION_DAYS = 365


def overdue(db: Session, now: datetime, days: int = RETENTION_DAYS) -> dict:
    cutoff = now - timedelta(days=days)
    cutoff_day = today_kst(now) - timedelta(days=days)

    bookings = db.execute(
        select(func.count(Booking.id), func.min(Slot.start_at))
        .join(Slot, Slot.id == Booking.slot_id)
        .where(Slot.start_at < cutoff)
    ).one()
    suggestions = db.execute(
        select(func.count(Suggestion.id), func.min(Suggestion.submitted_on))
        .where(Suggestion.submitted_on < cutoff_day)
    ).one()
    surveys = db.execute(
        select(Survey.id).where(Survey.closes_at.is_not(None), Survey.closes_at < cutoff)
        .order_by(Survey.id)
    ).scalars().all()
    tickets = db.execute(
        select(func.count(SupportTicket.id), func.min(SupportTicket.updated_at))
        .where(SupportTicket.updated_at < cutoff)
    ).one()
    return {
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "bookings": {"count": bookings[0], "oldest": _iso(bookings[1]),
                     "rule": "상담 예정일로부터 365일"},
        "suggestions": {"count": suggestions[0], "oldest": _iso(suggestions[1]),
                        "rule": "제출일로부터 365일"},
        "surveys": {"count": len(surveys), "ids": list(surveys),
                    "rule": "설문 종료 후 365일 (마감 시각이 있는 설문만 판별)"},
        "support_tickets": {"count": tickets[0], "oldest": _iso(tickets[1]),
                            "rule": "마지막 처리일로부터 365일"},
    }


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None
