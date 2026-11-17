"""Shared weekday-only scheduling policy; historic rows remain untouched."""
from datetime import datetime, timedelta, timezone

from app.core.errors import Conflict
from app.timeutil import KST


def touches_weekend(start: datetime, end: datetime) -> bool:
    """Check the whole half-open interval in KST, not the UTC start weekday.

    UTC is the storage convention for legacy naive database timestamps.
    An event ending exactly at Saturday 00:00 does not occupy Saturday.
    """
    start = (start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start).astimezone(KST)
    end = (end.replace(tzinfo=timezone.utc) if end.tzinfo is None else end).astimezone(KST)
    if end <= start:
        return start.weekday() >= 5
    day, last = start.date(), (end - timedelta(microseconds=1)).date()
    while day <= last:
        if day.weekday() >= 5:
            return True
        day += timedelta(days=1)
    return False


def ensure_weekday(start: datetime, end: datetime) -> None:
    if touches_weekend(start, end):
        raise Conflict("주말에는 상담 예약 및 강의를 등록할 수 없습니다", code="weekend_unavailable")
