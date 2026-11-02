"""한국 시간대 변환 유틸. 저장은 UTC, 입력·표시는 Asia/Seoul."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def kst_to_utc(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=KST).astimezone(timezone.utc)


def to_kst(dt: datetime) -> datetime:
    return dt.astimezone(KST)


def kst_date(dt: datetime) -> date:
    return to_kst(dt).date()


def today_kst(now: datetime) -> date:
    return to_kst(now).date()
