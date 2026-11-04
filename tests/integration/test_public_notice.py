from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings
from app.core.identity import VerifiedIdentity
from app.db import Base
from app.main import create_app
from app.models import AuditLog, AuthSession, User
from app.public_notice import NOTICE_VERSION


def setup_notice(tmp_path):
    settings = Settings(env="test", database_url=f"sqlite:///{tmp_path}/notice.db",
                        google_client_id="test-client", google_client_secret="test-secret",
                        public_notice_enabled=True, operator_name="Test <Operator>",
                        operator_affiliation="Test College", support_email="help@example.invalid")
    app = create_app(settings, identity_verifier=lambda *args: VerifiedIdentity(
        "google-public-student", "student@example.invalid", True, "Student"))
    Base.metadata.create_all(app.state.engine)
    return app, TestClient(app, follow_redirects=False)


@pytest.mark.parametrize("query", ["", "?consent_version=old&notice_ack=yes&transfer_ack=yes"])
def test_direct_login_without_consent_and_no_fabricated_consent(tmp_path, query):
    app, client = setup_notice(tmp_path)
    response = client.get("/auth/google/login" + query)
    assert response.status_code == 302
    with app.state.SessionLocal() as db:
        assert db.query(User).count() == db.query(AuthSession).count() == 0
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    assert client.get("/auth/google/callback", params={"code": "fake-code", "state": state}).status_code == 302
    me = client.get("/api/me").json()
    assert me["role"] == "student"
    assert client.get("/api/admin/users").status_code == 403
    with app.state.SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="user.notice_consent").count() == 0
        assert db.query(AuthSession).count() == 1


@pytest.mark.parametrize("failure", ["missing_cookie", "tampered_cookie", "wrong_state", "missing_code"])
def test_no_consent_flow_preserves_oauth_request_validation(tmp_path, failure):
    app, client = setup_notice(tmp_path)
    response = client.get("/auth/google/login")
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    if failure == "missing_cookie":
        client.cookies.clear()
    elif failure == "tampered_cookie":
        client.cookies.clear()
        client.cookies.set("cb_oauth", "tampered", path="/auth")
    response = client.get("/auth/google/callback", params={
        "code": "" if failure == "missing_code" else "fake",
        "state": "wrong" if failure == "wrong_state" else state})
    assert response.status_code == 401
    with app.state.SessionLocal() as db:
        assert db.query(User).count() == db.query(AuthSession).count() == 0
        assert db.query(AuditLog).count() == 0


def test_public_notice_escapes_operator_and_hides_when_disabled(tmp_path):
    app, client = setup_notice(tmp_path)
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "Test &lt;Operator&gt;" in response.text and "Test <Operator>" not in response.text
    assert "365일" in response.text and "싱가포르" in response.text
    assert "제15조 제1항 제4호" in response.text
    assert "동의로 간주하지 않습니다" in response.text
    assert "동의하지 않으면" not in response.text
    assert client.get("/api/auth/config").json()["notice"]["version"] == NOTICE_VERSION
    app.state.settings.public_notice_enabled = False
    assert client.get("/privacy").status_code == 404
    assert "notice" not in client.get("/api/auth/config").json()


def test_operator_required_when_notice_enabled():
    with pytest.raises(ConfigError):
        Settings(public_notice_enabled=True).validate()
