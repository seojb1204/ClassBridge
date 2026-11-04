"""세션 인증·CSRF·권한 의존성.

- 쿠키에는 임의 토큰만 담고, DB에는 SHA-256 해시를 저장한다.
- 역할은 매 요청마다 users 테이블에서 다시 읽는다 → 역할 변경이 즉시 반영된다.
- 역할 변경·비활성화 시 invalidate_user_sessions()로 기존 세션을 모두 삭제한다.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import P, has_permission
from app.db import get_db, utcnow
from app.models import AuthSession, User

SESSION_COOKIE = "cb_session"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass
class Principal:
    user: User
    session: AuthSession

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def role(self) -> str:
        return self.user.role

    def can(self, perm: P) -> bool:
        return has_permission(self.user.role, perm)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, ttl_hours: int) -> tuple[str, AuthSession]:
    raw = secrets.token_urlsafe(32)
    sess = AuthSession(
        token_hash=_hash(raw),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(hours=ttl_hours),
    )
    db.add(sess)
    return raw, sess


def set_session_cookie(response: Response, raw: str, secure: bool, ttl_hours: int) -> None:
    response.set_cookie(
        SESSION_COOKIE, raw, max_age=ttl_hours * 3600,
        httponly=True, secure=secure, samesite="lax", path="/",
    )


def clear_session_cookie(response: Response, secure: bool) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")


def invalidate_user_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def delete_session(db: Session, raw: str | None) -> None:
    if raw:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == _hash(raw)))


def get_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        raise Unauthorized("로그인이 필요합니다")
    row = db.execute(
        select(AuthSession, User)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == _hash(raw))
    ).first()
    if row is None:
        raise Unauthorized("세션이 만료되었거나 무효화되었습니다")
    sess, user = row
    if sess.expires_at <= utcnow():
        db.delete(sess)
        db.commit()
        raise Unauthorized("세션이 만료되었습니다")
    if not user.is_active:
        raise Unauthorized("비활성화된 계정입니다")
    # A valid session must not bypass a later staging allowlist change.
    # Checking on every request revokes access immediately without waiting
    # for the existing cookie's twelve-hour expiry.
    settings = request.app.state.settings
    if settings.staging_mode and user.email.lower() not in settings.staging_allowed_emails:
        raise Unauthorized("테스트 환경에 접근할 수 없는 계정입니다")
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not hmac.compare_digest(sent, sess.csrf_token):
            raise Forbidden("CSRF 토큰이 올바르지 않습니다", code="csrf")
    return Principal(user=user, session=sess)


def require(perm: P):
    """라우트에 권한을 선언한다. 선언 없는 /api 라우트는 테스트에서 실패한다 (기본 거부)."""

    def dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if not principal.can(perm):
            raise Forbidden("권한이 없습니다")
        return principal

    dependency.required_permission = perm  # type: ignore[attr-defined]
    return dependency


def require_login(principal: Principal = Depends(get_principal)) -> Principal:
    return principal


require_login.required_permission = "login"  # type: ignore[attr-defined]
