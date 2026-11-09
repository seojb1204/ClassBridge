"""Google 콜백 흐름 (실제 Google 대신 가짜 검증기 주입). 실제 Google 연동은 미검증 → 보고서에 구분."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.errors import Unauthorized
from app.core.identity import VerifiedIdentity
from app.db import Base, utcnow
from app.main import create_app
from app.models import AuthSession
from tests.conftest import make_settings


def _app(tmp_path, verifier):
    s = make_settings(f"sqlite:///{tmp_path}/g.db", google_client_id="cid", google_client_secret="sec")
    app = create_app(s, identity_verifier=verifier)
    Base.metadata.create_all(app.state.engine)
    return app


def test_google_login_flow(tmp_path):
    seen = {}

    def verifier(settings, code, nonce):
        seen["nonce"] = nonce
        return VerifiedIdentity(sub="g-123", email="Stu@Test.ac.kr", email_verified=True, name="구글학생")

    app = _app(tmp_path, verifier)
    c = TestClient(app, follow_redirects=False)
    r = c.get("/auth/google/login")
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["client_id"] == ["cid"] and q["scope"] == ["openid email profile"]
    r = c.get(f"/auth/google/callback?code=abc&state={q['state'][0]}")
    assert r.status_code == 302 and seen["nonce"] == q["nonce"][0]
    me = c.get("/api/me").json()
    assert me["email"] == "stu@test.ac.kr" and me["role"] == "student"


def test_survey_return_is_signed_and_only_local_numeric_id(tmp_path):
    app = _app(tmp_path, lambda s, c, n: VerifiedIdentity("qr-user", "qr@test.ac.kr", True))
    for target, expected in [("42", "/#/surveys/take/42"), ("https://evil.example", "/"), ("//evil", "/")]:
        c = TestClient(app, follow_redirects=False)
        r = c.get("/auth/google/login", params={"survey": target})
        state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
        r = c.get("/auth/google/callback", params={"state": state, "code": "ok", "survey": "999"})
        assert r.status_code == 302 and r.headers["location"] == expected


def test_state_mismatch_rejected(tmp_path):
    app = _app(tmp_path, lambda s, c, n: VerifiedIdentity("x", "x@test.ac.kr", True))
    c = TestClient(app, follow_redirects=False)
    c.get("/auth/google/login")
    assert c.get("/auth/google/callback?code=abc&state=forged").status_code == 401
    c2 = TestClient(app, follow_redirects=False)  # state 쿠키 없음
    assert c2.get("/auth/google/callback?code=abc&state=x").status_code == 401


def test_unverified_email_rejected(tmp_path):
    app = _app(tmp_path, lambda s, c, n: VerifiedIdentity("u", "u@test.ac.kr", False))
    c = TestClient(app, follow_redirects=False)
    q = parse_qs(urlparse(c.get("/auth/google/login").headers["location"]).query)
    assert c.get(f"/auth/google/callback?code=abc&state={q['state'][0]}").status_code == 403


def test_identity_bound_to_sub_not_email(tmp_path):
    """같은 이메일이라도 다른 Google sub이면 기존 계정에 로그인되지 않는다."""
    calls = iter([VerifiedIdentity("sub-A", "same@test.ac.kr", True), VerifiedIdentity("sub-B", "same@test.ac.kr", True)])
    app = _app(tmp_path, lambda s, c, n: next(calls))
    for expected in (302, 409):
        c = TestClient(app, follow_redirects=False)
        q = parse_qs(urlparse(c.get("/auth/google/login").headers["location"]).query)
        assert c.get(f"/auth/google/callback?code=abc&state={q['state'][0]}").status_code == expected


def test_verifier_failure_is_401(tmp_path):
    def bad(s, c, n):
        raise Unauthorized("ID 토큰 검증 실패")

    app = _app(tmp_path, bad)
    c = TestClient(app, follow_redirects=False)
    q = parse_qs(urlparse(c.get("/auth/google/login").headers["location"]).query)
    assert c.get(f"/auth/google/callback?code=abc&state={q['state'][0]}").status_code == 401


@pytest.mark.parametrize("remember", [False, True])
def test_remember_duration_is_signed_and_logout_revokes_session(tmp_path, remember):
    app = _app(tmp_path, lambda s, c, n: VerifiedIdentity("guest", "guest@test.ac.kr", True))
    client = TestClient(app, follow_redirects=False)
    login = client.get("/auth/google/login", params={"remember": remember, "survey": "42"})
    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
    callback = client.get("/auth/google/callback", params={"state": state, "code": "ok", "remember": not remember})
    ttl = (30 * 24 if remember else app.state.settings.session_ttl_hours) * 3600
    assert callback.headers["location"] == "/#/surveys/take/42"
    assert f"Max-Age={ttl}" in callback.headers["set-cookie"]
    from sqlalchemy.orm import Session
    with Session(app.state.engine) as db:
        remaining = (db.scalar(select(AuthSession)).expires_at - utcnow()).total_seconds()
        assert ttl - 10 < remaining <= ttl
    token = client.cookies.get("cb_session")
    csrf = client.get("/api/me").json()["csrf_token"]
    assert client.post("/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    client.cookies.set("cb_session", token)
    assert client.get("/api/me").status_code == 401
