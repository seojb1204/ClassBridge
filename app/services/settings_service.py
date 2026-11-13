"""관리자 운영 설정. 기본값 + 범위 검증."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.repositories import audit as audit_repo
from app.repositories import settings as settings_repo


@dataclass(frozen=True)
class Spec:
    default: int
    lo: int
    hi: int
    label: str


SPECS: dict[str, Spec] = {
    "booking_window_days": Spec(30, 1, 180, "예약 가능 범위(일)"),
    "booking_deadline_minutes": Spec(30, 0, 4320, "예약 신청·취소·변경 마감(상담 시작 N분 전)"),
    "default_break_minutes": Spec(0, 0, 120, "상담 간 기본 휴식(분)"),
    "survey_min_results": Spec(5, 1, 50, "설문 결과 공개 최소 응답 수"),
}


def get_settings(db: Session) -> dict[str, int]:
    stored = settings_repo.get_all(db)
    # The booking deadline is now canonical for all three actions. Retired
    # cancel_deadline_hours values (including custom values) stay in storage
    # for history, but cannot override the unified policy. Existing explicit
    # booking minutes, then non-default legacy booking hours, take precedence.

    legacy = stored.get("booking_deadline_hours")
    if type(legacy) is int and 0 <= legacy <= 72 and legacy != 3:
        stored.setdefault("booking_deadline_minutes", legacy * 60)
    out: dict[str, int] = {}
    for key, spec in SPECS.items():
        val = stored.get(key, spec.default)
        out[key] = val if isinstance(val, int) else spec.default
    return out


def describe() -> list[dict]:
    return [{"key": k, "label": s.label, "min": s.lo, "max": s.hi, "default": s.default} for k, s in SPECS.items()]


def update_settings(db: Session, actor_id: int, changes: dict[str, object]) -> dict[str, int]:
    changes = changes.copy()
    if "booking_deadline_hours" in changes:
        legacy = changes.pop("booking_deadline_hours")
        if type(legacy) is not int or not 0 <= legacy <= 72 or "booking_deadline_minutes" in changes:
            raise BadRequest("예약 신청 마감 시간을 확인해 주세요")
        changes["booking_deadline_minutes"] = legacy * 60
    before = get_settings(db)
    # Old clients may submit the retired cancellation setting. Never let a
    # stale separate value silently change the unified policy.
    if "cancel_deadline_hours" in changes:
        legacy_cancel = changes.pop("cancel_deadline_hours")
        target = changes.get("booking_deadline_minutes", before["booking_deadline_minutes"])
        if (type(legacy_cancel) not in (int, float)
                or legacy_cancel * 60 != target):
            raise BadRequest("취소·변경 마감은 예약 신청 마감(분)과 같습니다. 통합 마감 설정을 사용해 주세요")
    for key, value in changes.items():
        spec = SPECS.get(key)
        if spec is None:
            raise BadRequest(f"알 수 없는 설정: {key}")
        if not isinstance(value, int) or isinstance(value, bool) or not (spec.lo <= value <= spec.hi):
            raise BadRequest(f"{spec.label} 값은 {spec.lo}~{spec.hi} 사이 정수여야 합니다")
    for key, value in changes.items():
        settings_repo.put(db, key, value)
    audit_repo.add(db, actor_id, "settings.update", "settings", "",
                   {k: {"from": before[k], "to": v} for k, v in changes.items()})
    db.commit()
    return get_settings(db)
