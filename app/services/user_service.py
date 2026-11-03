"""로그인 시 사용자 등록·역할 부여, 관리자의 역할·계정 관리."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.core.auth import invalidate_user_sessions
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.identity import VerifiedIdentity
from app.db import utcnow
from app.models import User
from app.models.user import ROLES
from app.repositories import audit as audit_repo
from app.repositories import users as users_repo


def _initial_role(settings: Settings, email: str) -> str:
    if email in settings.admin_emails:
        return "admin"
    if email in settings.professor_emails:
        return "professor"
    return "student"


def _domain_allowed(settings: Settings, email: str) -> bool:
    if not settings.allowed_email_domains:
        return True
    return email.rsplit("@", 1)[-1] in settings.allowed_email_domains


def login_or_register(db: Session, settings: Settings, ident: VerifiedIdentity) -> User:
    if not ident.email_verified:
        raise Forbidden("이메일 인증이 완료된 Google 계정만 사용할 수 있습니다")
    email = ident.email.strip().lower()
    if settings.staging_mode and email not in settings.staging_allowed_emails:
        raise Forbidden("이 계정은 테스트 환경의 사용 허가 목록에 없습니다")
    user = users_repo.get_by_sub(db, ident.sub)

    if user is None:
        if users_repo.get_by_email(db, email) is not None:
            # 같은 이메일이 다른 Google 계정 ID에 묶여 있음 → 자동 병합하지 않는다
            raise Conflict("이미 다른 계정과 연결된 이메일입니다. 관리자에게 문의하세요")
        role = _initial_role(settings, email)
        if role == "student" and not _domain_allowed(settings, email):
            raise Forbidden("허용되지 않은 이메일 도메인입니다")
        user = User(google_sub=ident.sub, email=email, name=ident.name[:100], role=role)
        db.add(user)
        db.flush()
        if role != "student":
            audit_repo.add(db, None, "user.bootstrap_role", "user", user.id,
                           {"email": email, "role": role, "source": "env_allowlist"})
    else:
        if not user.is_active:
            raise Forbidden("비활성화된 계정입니다")
        if ident.name:
            user.name = ident.name[:100]
        # 최초 관리자 부여 보호: 환경변수 목록은 '활성 관리자가 한 명도 없을 때'만 승격에 쓰인다.
        if (email in settings.admin_emails and user.role != "admin"
                and users_repo.count_active_admins(db) == 0):
            old = user.role
            user.role = "admin"
            audit_repo.add(db, None, "user.bootstrap_role", "user", user.id,
                           {"email": email, "from": old, "role": "admin", "source": "env_allowlist_recovery"})
    user.last_login_at = utcnow()
    db.commit()
    return user


def _target(db: Session, user_id: int, lock: bool = False) -> User:
    user = users_repo.get_for_update(db, user_id) if lock else users_repo.get(db, user_id)
    if user is None:
        raise NotFound("사용자를 찾을 수 없습니다")
    return user


def _lock_and_get(db: Session, target_id: int) -> tuple[User, list[User]]:
    # 잠금 순서 고정: 활성 관리자들(id 순) → 대상. 교차 강등 시 교착 방지
    admins = users_repo.lock_active_admins(db)
    return _target(db, target_id, lock=True), admins


def _ensure_not_last_admin(target: User, admins: list[User]) -> None:
    if target.role == "admin" and target.is_active and len(admins) <= 1:
        raise Conflict("마지막 활성 관리자는 강등하거나 비활성화할 수 없습니다")


def change_role(db: Session, actor: User, target_id: int, new_role: str) -> User:
    if actor.role != "admin":  # 라우터 권한 검사와 별개로 서비스에서도 확인 (방어적 이중 검증)
        raise Forbidden("관리자만 역할을 변경할 수 있습니다")
    if new_role not in ROLES:
        raise BadRequest("올바르지 않은 역할입니다")
    if target_id == actor.id:
        raise Forbidden("자기 자신의 역할은 변경할 수 없습니다")
    target, admins = _lock_and_get(db, target_id)
    if target.role == new_role:
        db.rollback()
        return target
    _ensure_not_last_admin(target, admins)
    old = target.role
    target.role = new_role
    invalidate_user_sessions(db, target.id)  # 기존 세션 즉시 무효화
    audit_repo.add(db, actor.id, "user.role_change", "user", target.id,
                   {"email": target.email, "from": old, "to": new_role})
    db.commit()
    return target


def set_active(db: Session, actor: User, target_id: int, active: bool) -> User:
    if actor.role != "admin":
        raise Forbidden("관리자만 계정 상태를 변경할 수 있습니다")
    if target_id == actor.id:
        raise Forbidden("자기 자신의 계정은 비활성화할 수 없습니다")
    target, admins = _lock_and_get(db, target_id)
    if target.is_active == active:
        db.rollback()
        return target
    if not active:
        _ensure_not_last_admin(target, admins)
        invalidate_user_sessions(db, target.id)
    target.is_active = active
    audit_repo.add(db, actor.id, "user.activate" if active else "user.deactivate", "user", target.id,
                   {"email": target.email})
    db.commit()
    return target
