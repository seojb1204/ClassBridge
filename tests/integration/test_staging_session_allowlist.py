"""A staging session must be rejected as soon as its email loses allowlist access.

All requests run against disposable local test DBs. No deployed sessions are altered.
"""
from __future__ import annotations

import pytest

from app.models import Booking, Slot
from tests.conftest import ADMIN, PROF, login, make_slots


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


@pytest.mark.parametrize("role,email", [
    ("admin", ADMIN), ("prof", PROF), ("s1", "s1@test.ac.kr"),
])
def test_removed_role_cannot_cancel_booking_or_change_note(app, clients, role, email):
    slot_id = make_slots(clients["prof"])[0]
    created = clients["s1"].post("/api/bookings", json={"slot_id": slot_id})
    assert created.status_code == 201
    booking_id = created.json()["id"]
    assert clients["prof"].put(f"/api/bookings/{booking_id}/note",
                               json={"note": "private fixture note"}).status_code == 200
    settings = app.state.settings
    settings.staging_mode = True
    settings.dev_login_enabled = False
    settings.staging_allowed_emails = [ADMIN, PROF, "s1@test.ac.kr"]
    removed = clients[role]
    assert removed.get("/api/me").status_code == 200
    settings.staging_allowed_emails.remove(email)

    # Even privileged roles and valid CSRF tokens cannot bypass revocation.
    assert removed.get("/api/me").status_code == 401
    assert removed.post(f"/api/bookings/{booking_id}/cancel",
                        json={"reason": "revoked request"}).status_code == 401
    assert removed.put(f"/api/bookings/{booking_id}/note",
                       json={"note": "must not be saved"}).status_code == 401
    with app.state.SessionLocal() as db:
        booking = db.get(Booking, booking_id)
        assert booking.status == "booked"
        assert booking.professor_note == "private fixture note"
        assert db.get(Slot, slot_id).booked_count == 1


def test_empty_runtime_allowlist_denies_existing_session(app):
    client = login(app, ADMIN)
    app.state.settings.staging_mode = True
    app.state.settings.staging_allowed_emails = []
    assert client.get("/api/me").status_code == 401
