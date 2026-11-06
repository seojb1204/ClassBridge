"""역할별 권한표. 역할 상속에 기대지 않고 기능 단위 권한을 명시한다.

Admin은 Professor 권한 전체 + 관리자 전용 권한을 갖는다.
익명 응답 작성자 역추적 권한은 어떤 역할에도 존재하지 않는다 (만들지 않음).
"""
from __future__ import annotations

from enum import Enum


class P(str, Enum):
    # 공통
    SLOT_VIEW = "slot:view"
    # 학생
    BOOKING_SELF = "booking:self"
    SURVEY_RESPOND = "survey:respond"
    SUGGESTION_SUBMIT = "suggestion:submit"
    # 교수자
    SLOT_MANAGE = "slot:manage"
    BOOKING_MANAGE = "booking:manage"
    CONSULT_NOTE = "booking:note"
    SURVEY_MANAGE = "survey:manage"
    SURVEY_RESULTS = "survey:results"
    SUGGESTION_READ = "suggestion:read"
    AI_ANALYZE = "ai:analyze"
    EXPORT = "data:export"
    ANNOUNCEMENT_MANAGE = "announcement:manage"
    # 관리자 전용
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_VIEW = "audit:view"
    SUPPORT_MANAGE = "support:manage"


STUDENT = frozenset({P.SLOT_VIEW, P.BOOKING_SELF, P.SURVEY_RESPOND, P.SUGGESTION_SUBMIT})

PROFESSOR = frozenset({
    P.SLOT_VIEW, P.SLOT_MANAGE, P.BOOKING_MANAGE, P.CONSULT_NOTE,
    P.SURVEY_MANAGE, P.SURVEY_RESULTS, P.SUGGESTION_READ, P.AI_ANALYZE, P.EXPORT, P.ANNOUNCEMENT_MANAGE,
})

ADMIN = PROFESSOR | frozenset({P.USER_MANAGE, P.ROLE_MANAGE, P.SETTINGS_MANAGE, P.AUDIT_VIEW, P.SUPPORT_MANAGE})

ROLE_PERMISSIONS: dict[str, frozenset[P]] = {
    "student": STUDENT,
    "professor": PROFESSOR,
    "admin": ADMIN,
}


def has_permission(role: str, perm: P) -> bool:
    # 알 수 없는 역할은 빈 집합 → 기본 거부
    return perm in ROLE_PERMISSIONS.get(role, frozenset())


def permissions_for(role: str) -> list[str]:
    return sorted(p.value for p in ROLE_PERMISSIONS.get(role, frozenset()))
