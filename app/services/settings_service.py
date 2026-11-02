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
    "booking_deadline_hours": Spec(3, 0, 72, "예약 신청 마감(상담 시작 N시간 전)"),
    "cancel_deadline_hours": Spec(3, 0, 72, "학생 취소 마감(상담 시작 N시간 전)"),
    "default_break_minutes": Spec(0, 0, 120, "상담 간 기본 휴식(분)"),
    "survey_min_results": Spec(5, 1, 50, "설문 결과 공개 최소 응답 수"),
}


def get_settings(db: Session) -> dict[str, int]:
    stored = settings_repo.get_all(db)
    out: dict[str, int] = {}
    for key, spec in SPECS.items():
        val = stored.get(key, spec.default)
        out[key] = val if isinstance(val, int) else spec.default
    return out


def describe() -> list[dict]:
    return [{"key": k, "label": s.label, "min": s.lo, "max": s.hi, "default": s.default} for k, s in SPECS.items()]


def update_settings(db: Session, actor_id: int, changes: dict[str, object]) -> dict[str, int]:
    before = get_settings(db)
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
