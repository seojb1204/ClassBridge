"""Explicitly public, token-scoped surveys. Login cookies are never read here."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, NotFound
from app.db import get_db, utcnow
from app.models import GuestParticipation, Survey
from app.routers.surveys import feature_on
from app.schemas.surveys import QuestionOut, SubmitIn
from app.services import survey_service as svc

router = APIRouter(prefix="/api/public-surveys", tags=["public-surveys"], dependencies=[Depends(feature_on)])
COOKIE = "cb_survey_guest"
TTL = 365 * 24 * 3600


def _survey(db, token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{32}", token):
        raise NotFound("설문을 찾을 수 없습니다")
    s = db.scalar(select(Survey).where(Survey.public_token == token, Survey.access_mode == "anonymous",
                                     Survey.deleted_at.is_(None), Survey.status != "draft"))
    if not s:
        raise NotFound("설문을 찾을 수 없습니다")
    return s


def _signer(request):
    return URLSafeTimedSerializer(request.app.state.settings.secret_key, salt="survey-guest-v1")


def _guest(request):
    try:
        value = _signer(request).loads(request.cookies.get(COOKIE, ""), max_age=TTL)
        return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{32}", value) else None
    except BadSignature:
        return None


def _digest(request, purpose, guest, token):
    return hmac.new(request.app.state.settings.secret_key.encode(),
                    f"{purpose}:{guest}:{token}".encode(), hashlib.sha256).hexdigest()


@router.get("/{token}")
def read(token: str, request: Request, db: Session = Depends(get_db)):
    s = _survey(db, token)
    guest = _guest(request)
    fresh = guest is None
    guest = guest or secrets.token_urlsafe(24)
    browser_hash = _digest(request, "participation", guest, token)
    done = db.get(GuestParticipation, (s.id, browser_hash)) is not None
    result = JSONResponse({"id": s.id, "title": s.title, "description": s.description,
                           "access_mode": "anonymous", "participated": done, "is_open": svc.is_open(s, utcnow()),
                           "questions": [QuestionOut.model_validate(q).model_dump() for q in s.questions],
                           "csrf_token": _digest(request, "csrf", guest, token)})
    if fresh:
        result.set_cookie(COOKIE, _signer(request).dumps(guest), max_age=TTL, httponly=True,
                          secure=request.app.state.settings.cookie_secure, samesite="lax", path="/api/public-surveys")
    return result


@router.post("/{token}/responses", status_code=201)
def submit(token: str, body: SubmitIn, request: Request, db: Session = Depends(get_db)):
    s = _survey(db, token)
    guest = _guest(request)
    if not guest or not hmac.compare_digest(request.headers.get("X-Survey-CSRF", ""),
                                            _digest(request, "csrf", guest, token)):
        raise Forbidden("설문을 다시 열어 주세요. 쿠키 허용이 필요합니다", code="csrf")
    browser_hash = _digest(request, "participation", guest, token)
    request.app.state.public_survey_limiter.hit(browser_hash)
    svc.submit(db, None, s.id, body.answers, browser_hash=browser_hash)
    return {"ok": True, "message": "응답이 제출되었습니다. 감사합니다."}
