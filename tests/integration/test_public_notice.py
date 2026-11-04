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


@pytest.mark.parametrize("query", ["", "?consent_version=old&notice_ack=yes&transfer_ack=yes",
                                   f"?consent_version={NOTICE_VERSION}&notice_ack=yes",
                                   f"?consent_version={NOTICE_VERSION}&transfer_ack=yes"])
def test_notice_cannot_be_skipped(tmp_path, query):
    app, client = setup_notice(tmp_path)
    assert client.get("/auth/google/login" + query).status_code == 400
    with app.state.SessionLocal() as db:
        assert db.query(User).count() == db.query(AuthSession).count() == 0


def test_public_login_creates_student_and_records_consent(tmp_path):
    app, client = setup_notice(tmp_path)
    response = client.get(f"/auth/google/login?consent_version={NOTICE_VERSION}&notice_ack=yes&transfer_ack=yes")
    assert response.status_code == 302
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    assert client.get("/auth/google/callback", params={"code": "fake-code", "state": state}).status_code == 302
    me = client.get("/api/me").json()
    assert me["role"] == "student"
    assert client.get("/api/admin/users").status_code == 403
    with app.state.SessionLocal() as db:
        log = db.query(AuditLog).filter_by(action="user.notice_consent").one()
        assert log.actor_id == me["id"]
        assert log.detail == {"version": NOTICE_VERSION, "collection_use": True, "overseas_processing": True}


def test_old_oauth_cookie_cannot_skip_new_notice(tmp_path):
    app, client = setup_notice(tmp_path)
    app.state.settings.public_notice_enabled = False
    response = client.get("/auth/google/login")
    state = parse_qs(urlparse(response.headers["location"]).query)["state"][0]
    app.state.settings.public_notice_enabled = True
    assert client.get("/auth/google/callback", params={"code": "fake", "state": state}).status_code == 401
    with app.state.SessionLocal() as db:
        assert db.query(User).count() == 0


def test_public_notice_escapes_operator_and_hides_when_disabled(tmp_path):
    app, client = setup_notice(tmp_path)
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "Test &lt;Operator&gt;" in response.text and "Test <Operator>" not in response.text
    assert "365일" in response.text and "싱가포르" in response.text
    assert client.get("/api/auth/config").json()["notice"]["version"] == NOTICE_VERSION
    app.state.settings.public_notice_enabled = False
    assert client.get("/privacy").status_code == 404
    assert "notice" not in client.get("/api/auth/config").json()


def test_operator_required_when_notice_enabled():
    with pytest.raises(ConfigError):
        Settings(public_notice_enabled=True).validate()
