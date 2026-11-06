from datetime import timedelta
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.db import utcnow
from app.infra.gmail import MailFailure, message_for
from app.models import Booking, Notification
from app.services.notifications import claim, deliver_one
from tests.conftest import make_slots


def enable(app):
    s = app.state.settings
    s.gmail_notifications_enabled = True
    s.gmail_sender_email = "sender@example.com"
    s.gmail_professor_email = "professor@example.com"
    return s


def rows(app):
    with app.state.SessionLocal() as db:
        return list(db.scalars(select(Notification).order_by(Notification.id)))


def test_book_change_cancel_and_minimal_named_mail(app, clients):
    enable(app)
    ids = make_slots(clients["prof"])
    b = clients["s1"].post("/api/bookings", json={"slot_id": ids[0], "applicant_name": "신청학생",
                "student_number": "PRIVATE-STUDENT-NUMBER", "topic": "PRIVATE-TOPIC"}).json()
    changed = clients["s1"].post(f"/api/bookings/{b['id']}/reschedule", json={"new_slot_id": ids[1]}).json()
    assert clients["s1"].post(f"/api/bookings/{changed['id']}/cancel", json={"reason": "PRIVATE-REASON"}).status_code == 200
    queue = rows(app)
    assert [r.payload["kind"] for r in queue] == ["created", "changed", "cancelled"]
    assert len({r.chain_id for r in queue}) == 1
    assert queue[1].payload["old_id"] == b["id"]
    for row in queue:
        msg = message_for(row)
        text = msg.get_content()
        assert "신청학생" in text
        assert "PRIVATE" not in text and "s1@" not in text
        assert msg["To"] == "professor@example.com" and not msg["Cc"] and not msg["Bcc"]
        assert text.rstrip().endswith("정보가 아닙니다.")


def test_proxy_and_force_slot_cancel_and_slot_change(app, clients):
    enable(app)
    p = clients["prof"]
    ids = make_slots(p, kind="group", capacity=2)
    for who in ("s1", "s2"):
        assert p.post("/api/bookings", json={"slot_id": ids[0], "student_id": clients[who].me["id"]}).status_code == 201
    assert p.patch(f"/api/slots/{ids[0]}", json={"location": "PRIVATE-LOCATION"}).status_code == 200
    assert p.post(f"/api/slots/{ids[0]}/cancel", json={"force": True, "reason": "PRIVATE-REASON"}).status_code == 200
    assert p.post(f"/api/slots/{ids[0]}/cancel", json={"force": True, "reason": "duplicate"}).status_code == 200
    queue = rows(app)
    assert [r.payload["kind"] for r in queue] == ["created"] * 2 + ["slot_changed"] * 2 + ["cancelled"] * 2
    assert all("PRIVATE" not in str(r.payload) for r in queue)


def test_disabled_and_rejected_requests_do_not_enqueue(app, clients):
    ids = make_slots(clients["prof"])
    b = clients["s1"].post("/api/bookings", json={"slot_id": ids[0]}).json()
    assert not rows(app)
    enable(app)
    assert clients["s2"].post(f"/api/bookings/{b['id']}/cancel", json={}).status_code == 404
    assert clients["s2"].post("/api/bookings", json={"slot_id": ids[0]}).status_code == 409
    assert clients["s1"].post("/api/bookings", json={"slot_id": ids[1]}).status_code == 409
    assert not rows(app)
    assert clients["s1"].post(f"/api/bookings/{b['id']}/cancel", json={}).status_code == 200
    assert clients["s1"].post(f"/api/bookings/{b['id']}/cancel", json={}).status_code == 409
    assert len(rows(app)) == 1


def test_transaction_failure_rolls_back_booking_and_outbox(app, clients, monkeypatch):
    enable(app)
    slot = make_slots(clients["prof"])[0]
    from sqlalchemy.orm import Session
    original = Session.commit
    def fail_commit(db):
        if any(isinstance(x, Notification) for x in db.new):
            raise RuntimeError("simulated commit failure")
        return original(db)
    monkeypatch.setattr(Session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated"):
        clients["s1"].post("/api/bookings", json={"slot_id": slot})
    assert not rows(app)
    with app.state.SessionLocal() as db:
        assert not list(db.scalars(select(Booking)))


@pytest.mark.parametrize("state,code", [("pending", "rate_limited"), ("reauth", "token_rejected"),
                                       ("uncertain", "send_network_unknown"), ("failed", "send_rejected")])
def test_failures_do_not_reverse_successful_booking(app, clients, state, code):
    settings = enable(app)
    slot = make_slots(clients["prof"])[0]
    b = clients["s1"].post("/api/bookings", json={"slot_id": slot})
    assert b.status_code == 201
    sender = Mock()
    sender.send.side_effect = MailFailure(state, code)
    assert deliver_one(app.state.SessionLocal, sender, settings)
    assert rows(app)[0].status == state
    with app.state.SessionLocal() as db:
        assert db.get(Booking, b.json()["id"]).status == "booked"
    assert not deliver_one(app.state.SessionLocal, sender, settings)
    assert sender.send.call_count == 1


def test_chain_order_crash_recovery_and_admin_review(app, clients):
    settings = enable(app)
    slot = make_slots(clients["prof"])[0]
    b = clients["s1"].post("/api/bookings", json={"slot_id": slot}).json()
    clients["s1"].post(f"/api/bookings/{b['id']}/cancel", json={})
    first = claim(app.state.SessionLocal)
    assert first and first.status == "sending"
    assert claim(app.state.SessionLocal) is None
    assert claim(app.state.SessionLocal, utcnow() + timedelta(minutes=4)) is None
    assert rows(app)[0].status == "uncertain"
    url = f"/api/admin/notifications/{first.id}/resolve"
    assert clients["prof"].post(url, json={"action": "retry", "acknowledge": True}).status_code == 403
    assert clients["admin"].post(url, json={"action": "retry"}).status_code == 400
    assert clients["admin"].post(url, json={"action": "confirmed_sent", "acknowledge": True}).status_code == 200
    sender = Mock()
    sender.send.return_value = "gmail-accepted-id"
    assert deliver_one(app.state.SessionLocal, sender, settings)
    assert [r.status for r in rows(app)] == ["sent", "sent"]
    assert not deliver_one(app.state.SessionLocal, sender, settings)
    result = clients["admin"].get("/api/admin/notifications").json()
    assert result["counts"] == {"sent": 2} and result["last_success"]


def test_retry_limit_and_no_secrets_in_admin_response(app, clients):
    settings = enable(app)
    settings.gmail_refresh_token = "SECRET-REFRESH"
    settings.gmail_client_secret = "SECRET-CLIENT"
    slot = make_slots(clients["prof"])[0]
    clients["s1"].post("/api/bookings", json={"slot_id": slot})
    with app.state.SessionLocal() as db:
        row = db.scalar(select(Notification))
        row.attempts = 7
        db.commit()
    sender = Mock()
    sender.send.side_effect = MailFailure("pending", "rate_limited")
    deliver_one(app.state.SessionLocal, sender, settings)
    assert rows(app)[0].status == "failed"
    response = clients["admin"].get("/api/admin/notifications")
    assert "SECRET" not in response.text and "student_name" not in response.text
    assert clients["s1"].get("/api/admin/notifications").status_code == 403
    assert clients["prof"].get("/api/admin/notifications").status_code == 403
    assert response.status_code == 200


def test_failed_reschedule_rolls_back_without_additional_notification(app, clients):
    enable(app)
    ids = make_slots(clients["prof"])
    first = clients["s1"].post("/api/bookings", json={"slot_id": ids[0]}).json()
    clients["s2"].post("/api/bookings", json={"slot_id": ids[1]})
    response = clients["s1"].post(f"/api/bookings/{first['id']}/reschedule", json={"new_slot_id": ids[1]})
    assert response.status_code == 409
    assert len(rows(app)) == 2
    with app.state.SessionLocal() as db:
        assert db.get(Booking, first["id"]).status == "booked"
