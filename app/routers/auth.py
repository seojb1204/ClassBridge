"""로그인/로그아웃 및 현재 사용자 정보."""
from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app.core.auth import (
    SESSION_COOKIE,
    Principal,
    clear_session_cookie,
    create_session,
    delete_session,
    require_login,
    set_session_cookie,
)
from app.core.errors import NotFound, Unauthorized
from app.core.identity import VerifiedIdentity
from app.core.permissions import permissions_for
from app.db import get_db
from app.infra import google_oauth
from app.public_notice import NOTICE_VERSION, render_notice
from app.schemas.users import DevLoginIn, MeOut
from app.services import user_service

router = APIRouter()
OAUTH_COOKIE = "cb_oauth"


def _signer(request: Request) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(request.app.state.settings.secret_key, salt="oauth-state")


def _start_session(request: Request, db: Session, user, response, *, remember: bool = False) -> None:
    s = request.app.state.settings
    ttl_hours = 30 * 24 if remember else s.session_ttl_hours
    raw, _ = create_session(db, user, ttl_hours)
    db.commit()
    set_session_cookie(response, raw, s.cookie_secure, ttl_hours)


@router.get("/auth/google/login", include_in_schema=False)
def google_login(request: Request, survey: str = "", remember: bool = False):
    s = request.app.state.settings
    if not s.google_client_id:
        raise NotFound("Google 로그인이 설정되지 않았습니다")
    state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    resp = RedirectResponse(google_oauth.build_auth_url(s, state, nonce), status_code=302)
    payload = {"state": state, "nonce": nonce, "remember": remember}
    if re.fullmatch(r"[1-9][0-9]{0,9}", survey):
        payload["survey"] = survey
    resp.set_cookie(OAUTH_COOKIE, _signer(request).dumps(payload),
                    max_age=600, httponly=True, secure=s.cookie_secure, samesite="lax", path="/auth")
    return resp


@router.get("/auth/google/callback", include_in_schema=False)
def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    s = request.app.state.settings
    try:
        data = _signer(request).loads(request.cookies.get(OAUTH_COOKIE, ""), max_age=600)
    except BadSignature as exc:
        raise Unauthorized("로그인 요청이 만료되었습니다. 다시 시도하세요") from exc
    if not code or not secrets.compare_digest(state, data.get("state", "")):
        raise Unauthorized("state 불일치")
    verifier = request.app.state.identity_verifier
    ident = verifier(s, code, data["nonce"])
    user = user_service.login_or_register(db, s, ident)
    survey = data.get("survey", "")
    target = f"/#/surveys/take/{survey}" if re.fullmatch(r"[1-9][0-9]{0,9}", survey) else "/"
    resp = RedirectResponse(target, status_code=302)
    resp.delete_cookie(OAUTH_COOKIE, path="/auth")
    _start_session(request, db, user, resp, remember=data.get("remember") is True)
    return resp


@router.post("/auth/dev/login", include_in_schema=False)
def dev_login(body: DevLoginIn, request: Request, db: Session = Depends(get_db)):
    """개발·테스트 전용. 운영 환경에서는 설정 검증 단계에서 켤 수 없다.
    역할은 요청값이 아니라 서버의 이메일 허용 목록으로만 결정된다."""
    s = request.app.state.settings
    if not s.dev_login_enabled or s.is_production:
        raise NotFound("Not Found")
    email = body.email.strip().lower()
    ident = VerifiedIdentity(sub=f"dev:{email}", email=email, email_verified=True,
                                          name=body.name or email.split("@")[0])
    user = user_service.login_or_register(db, s, ident)
    resp = JSONResponse({"ok": True})
    _start_session(request, db, user, resp, remember=body.remember)
    return resp


@router.post("/auth/logout")
def logout(request: Request, principal: Principal = Depends(require_login), db: Session = Depends(get_db)):
    delete_session(db, request.cookies.get(SESSION_COOKIE))
    db.commit()
    resp = JSONResponse({"ok": True})
    clear_session_cookie(resp, request.app.state.settings.cookie_secure)
    return resp


@router.get("/api/me", response_model=MeOut)
def me(request: Request, principal: Principal = Depends(require_login)):
    s = request.app.state.settings
    u = principal.user
    return MeOut(
        id=u.id, email=u.email, name=u.name, role=u.role,
        permissions=permissions_for(u.role), csrf_token=principal.session.csrf_token,
        features={"surveys": s.feature_surveys, "suggestions": s.feature_suggestions, "ai": s.ai_mode},
    )


@router.get("/api/auth/config")
def auth_config(request: Request):
    """로그인 화면용 공개 정보 (비밀 없음)."""
    s = request.app.state.settings
    result = {"google": bool(s.google_client_id), "dev_login": s.dev_login_enabled and not s.is_production}
    result["suggestions"] = s.feature_suggestions
    if s.public_notice_enabled:
        result["notice"] = {"version": NOTICE_VERSION, "url": "/privacy", "support_email": s.support_email}
    return result


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
def privacy_notice(request: Request):
    settings = request.app.state.settings
    if not settings.public_notice_enabled:
        raise NotFound("Not Found")
    return HTMLResponse(render_notice(settings))


auth_config.public = True  # type: ignore[attr-defined]
