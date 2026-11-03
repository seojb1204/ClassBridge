"""Google OpenID Connect 로그인 (Authorization Code 흐름).

ID 토큰 서명·aud·iss·exp 검증은 검증된 라이브러리(google-auth)에 맡긴다.
"""
from __future__ import annotations

from typing import Protocol
from urllib.parse import urlencode

import httpx

from app.config import Settings
from app.core.errors import Unauthorized
from app.core.identity import VerifiedIdentity

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
VALID_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def redirect_uri(settings: Settings) -> str:
    return f"{settings.base_url}/auth/google/callback"


def build_auth_url(settings: Settings, state: str, nonce: str) -> str:
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


class IdentityVerifier(Protocol):
    def __call__(self, settings: Settings, code: str, nonce: str) -> VerifiedIdentity: ...


def verify_with_google(settings: Settings, code: str, nonce: str) -> VerifiedIdentity:
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    resp = httpx.post(TOKEN_ENDPOINT, data={
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri(settings),
        "grant_type": "authorization_code",
    }, timeout=10)
    if resp.status_code != 200:
        raise Unauthorized("Google 인증 코드 교환에 실패했습니다")
    raw = resp.json().get("id_token")
    if not raw:
        raise Unauthorized("ID 토큰이 없습니다")
    try:
        claims = id_token.verify_oauth2_token(raw, g_requests.Request(), settings.google_client_id)
    except ValueError as exc:
        raise Unauthorized("ID 토큰 검증 실패") from exc
    if claims.get("iss") not in VALID_ISSUERS:
        raise Unauthorized("발급자가 올바르지 않습니다")
    if claims.get("nonce") != nonce:
        raise Unauthorized("nonce 불일치")
    return VerifiedIdentity(
        sub=str(claims["sub"]),
        email=str(claims.get("email", "")),
        email_verified=bool(claims.get("email_verified")),
        name=str(claims.get("name", "")),
    )
