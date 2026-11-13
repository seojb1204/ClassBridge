"""예약 정책 순수 함수 (DB 없이 단위 테스트 가능)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.core.errors import BadRequest, Conflict
from app.timeutil import kst_to_utc

MAX_SLOTS_PER_REQUEST = 300

TRANSITIONS: dict[str, set[str]] = {
    "booked": {"cancelled", "completed", "no_show"},
    "completed": {"no_show"},
    "no_show": {"completed"},
    "expired": {"completed", "no_show"},
    "cancelled": set(),
}


@dataclass(frozen=True)
class Policy:
    booking_window_days: int
    booking_deadline_minutes: int

    @classmethod
    def from_settings(cls, s: dict[str, int]) -> "Policy":
        return cls(s["booking_window_days"], s["booking_deadline_minutes"])


def generate_blocks(days: list[date], start: time, end: time, duration_min: int,
                    break_min: int) -> list[tuple[datetime, datetime]]:
    """한국 시간 기준 날짜·시각 범위를 상담 블록(UTC)으로 쪼갠다."""
    if duration_min < 5 or duration_min > 240:
        raise BadRequest("상담 1회 시간은 5~240분이어야 합니다")
    if break_min < 0 or break_min > 120:
        raise BadRequest("휴식 시간은 0~120분이어야 합니다")
    if end <= start:
        raise BadRequest("종료 시각은 시작 시각보다 늦어야 합니다")
    blocks: list[tuple[datetime, datetime]] = []
    step = timedelta(minutes=duration_min + break_min)
    dur = timedelta(minutes=duration_min)
    for d in sorted(set(days)):
        cur = kst_to_utc(d, start)
        stop = kst_to_utc(d, end)
        while cur + dur <= stop:
            blocks.append((cur, cur + dur))
            cur += step
            if len(blocks) > MAX_SLOTS_PER_REQUEST:
                raise BadRequest(f"한 번에 최대 {MAX_SLOTS_PER_REQUEST}개까지 생성할 수 있습니다")
    if not blocks:
        raise BadRequest("주어진 범위로 만들 수 있는 상담 시간이 없습니다")
    return blocks


def expand_days(start_date: date, weekdays: list[int] | None, repeat_weeks: int) -> list[date]:
    """start_date부터 repeat_weeks주 동안 지정 요일(0=월)을 펼친다. weekdays 없으면 start_date 요일만."""
    if repeat_weeks < 1 or repeat_weeks > 26:
        raise BadRequest("반복 주 수는 1~26이어야 합니다")
    wds = set(weekdays) if weekdays else {start_date.weekday()}
    if any(w < 0 or w > 6 for w in wds):
        raise BadRequest("요일 값이 올바르지 않습니다")
    return [start_date + timedelta(days=i) for i in range(repeat_weeks * 7)
            if (start_date + timedelta(days=i)).weekday() in wds]


def check_student_booking_time(slot_start: datetime, now: datetime, policy: Policy) -> None:
    if slot_start <= now:
        raise Conflict("이미 지난 상담 시간입니다", code="slot_past")
    if slot_start - now < timedelta(minutes=policy.booking_deadline_minutes):
        raise Conflict(f"상담 시작 {policy.booking_deadline_minutes}분 전까지만 예약할 수 있습니다",
                       code="booking_deadline")
    if slot_start - now > timedelta(days=policy.booking_window_days):
        raise Conflict(f"{policy.booking_window_days}일 이내의 상담만 예약할 수 있습니다",
                       code="booking_window")


def check_student_cancel_time(slot_start: datetime, now: datetime, policy: Policy) -> None:
    if slot_start - now < timedelta(minutes=policy.booking_deadline_minutes):
        raise Conflict(f"상담 시작 {policy.booking_deadline_minutes}분 전까지만 취소·변경할 수 있습니다",
                       code="cancel_deadline")


def check_transition(current: str, target: str) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise Conflict(f"'{current}' 상태에서 '{target}'(으)로 변경할 수 없습니다", code="bad_transition")
