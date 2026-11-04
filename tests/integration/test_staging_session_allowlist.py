"""A staging session must be rejected as soon as its email loses allowlist access.

All requests run against disposable local test DBs. No deployed sessions are altered.
"""
from __future__ import annotations

from tests.conftest import ADMIN, PROF, login


def test_existing_session_cannot_bypass_new_staging_allowlist(app):
    admin = login(app, ADMIN)
    professor = login(app, PROF)
    student = login(app, "outside@test.ac.kr")

    # The student has a valid session issued *before* the staging restriction.
    assert student.get("/api/me").status_code == 200
    settings = app.state.settings
    settings.staging_mode = True
    settings.staging_allowed_emails = [ADMIN, PROF]
    settings.dev_login_enabled = False

    # Privileged, explicitly approved users remain available.
    assert admin.get("/api/me").status_code == 200
    assert professor.get("/api/me").status_code == 200
    # But revoked users cannot use even their previously issued session.
    assert student.get("/api/me").status_code == 401
    assert student.get("/api/bookings/mine").status_code == 401
    assert student.get("/api/slots?start=2030-01-01").status_code == 401

    # This does not delete users, bookings, or sessions; if reapproved, they
    # can resume without exposing another user's protected information.
    settings.staging_allowed_emails.append("outside@test.ac.kr")
    assert student.get("/api/me").status_code == 200


def test_development_mode_without_staging_keeps_existing_sessions(app):
    client = login(app, "ordinary@test.ac.kr")
    app.state.settings.staging_mode = False
    app.state.settings.staging_allowed_emails = []
    assert client.get("/api/me").status_code == 200
