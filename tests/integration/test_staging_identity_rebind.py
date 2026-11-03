"""Regression tests for safe staging Google identity linking."""
from __future__ import annotations

import pytest

from app.core.errors import Conflict
from app.core.identity import VerifiedIdentity
from app.models import User
from app.services import user_service
from tests.conftest import ADMIN, PROF, login


def test_staging_admin_rebind_preserves_identity_and_revokes_session(app):
    client = login(app, ADMIN)
    existing_id = client.me["id"]
    settings = app.state.settings
    settings.staging_mode = True
    settings.staging_allowed_emails = [ADMIN, PROF]
    settings.dev_login_enabled = False
    db = app.state.SessionLocal()
    try:
        linked = user_service.login_or_register(db, settings, VerifiedIdentity(
            sub="google-verified-123", email=ADMIN, email_verified=True, name="관리자"))
        assert linked.id == existing_id
        assert linked.role == "admin"
        assert linked.google_sub == "google-verified-123"
        assert db.query(User).count() == 1
        with pytest.raises(Conflict):
            user_service.login_or_register(db, settings, VerifiedIdentity(
                sub="another-google-sub", email=ADMIN, email_verified=True))
    finally:
        db.close()
    assert client.get("/api/me").status_code == 401


def test_normal_environment_does_not_merge_different_identities(app):
    c = login(app, ADMIN)
    db = app.state.SessionLocal()
    try:
        with pytest.raises(Conflict):
            user_service.login_or_register(db, app.state.settings, VerifiedIdentity(
                sub="google-not-staging", email=ADMIN, email_verified=True))
        assert db.get(User, c.me["id"]).google_sub.startswith("dev:")
    finally:
        db.close()
