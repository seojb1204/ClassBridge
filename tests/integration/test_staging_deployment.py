"""Fail-closed staging account policy and separate migration connection verification."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings
from tests.conftest import ADMIN, PROF, build_app

ROOT = Path(__file__).resolve().parents[2]


def test_staging_mode_requires_explicit_allowlist():
    with pytest.raises(ConfigError, match="STAGING_ALLOWED_EMAILS"):
        Settings(staging_mode=True, admin_emails=[ADMIN]).validate()
    with pytest.raises(ConfigError, match="admin/professor"):
        Settings(staging_mode=True, admin_emails=[ADMIN],
                 staging_allowed_emails=["student@test.ac.kr"]).validate()


def test_staging_bootstrap_allows_no_google_credentials_but_not_partial_oauth():
    allowed = dict(env="production", database_url="postgresql+psycopg://localhost/test",
                   secret_key="secure-not-production-testing-only-00000000",
                   cookie_secure=True, admin_emails=[ADMIN],
                   professor_emails=[PROF], staging_mode=True,
                   staging_allowed_emails=[ADMIN, PROF])
    Settings(**allowed).validate()
    with pytest.raises(ConfigError, match="GOOGLE_CLIENT"):
        Settings(**allowed, google_client_id="partially-configured").validate()
    non_staging = {**allowed, "staging_mode": False}
    with pytest.raises(ConfigError, match="GOOGLE_CLIENT"):
        Settings(**non_staging).validate()


def test_only_staging_approved_google_accounts_can_sign_in(tmp_path):
    app = build_app(str("sqlite:///" + str(tmp_path / "staging.db")),
                    staging_mode=True, admin_emails=[ADMIN],
                    professor_emails=[PROF],
                    staging_allowed_emails=[ADMIN, PROF, "student@test.ac.kr"])
    try:
        denied = TestClient(app).post("/auth/dev/login", json={"email": "unknown@gmail.com"})
        assert denied.status_code == 403
        approved = TestClient(app).post("/auth/dev/login", json={"email": "student@test.ac.kr"})
        assert approved.status_code == 200
    finally:
        app.state.engine.dispose()


def test_direct_database_url_used_for_migrations(tmp_path):
    """The app may use a pooled URL, but Alembic should use a separate direct URL."""
    app_db = tmp_path / "application.sqlite"
    direct_db = tmp_path / "direct.sqlite"
    env = dict(os.environ,
               DATABASE_URL=f"sqlite:///{app_db}",
               DATABASE_URL_DIRECT=f"sqlite:///{direct_db}")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=ROOT, env=env, check=True, capture_output=True, text=True)
    with sqlite3.connect(direct_db) as conn:
        assert conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()[0] == 1
    assert not app_db.exists()
