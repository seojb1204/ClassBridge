import base64
import json
from datetime import timedelta
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select

from app.db import utcnow
from app.infra.gmail import MailFailure
from app.infra.push import PushSender
from app.models import AuthSession, Notification, PushSubscription
from app.services.notifications import deliver_one
from tests.conftest import make_slots


def subscription(token="device"):
    key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    def enc(v):
        return base64.urlsafe_b64encode(v).decode().rstrip("=")
    return {"endpoint": "https://fcm.googleapis.com/fcm/send/" + token,
            "keys": {"p256dh": enc(key), "auth": enc(b"a" * 16)}}


def enable(app):
    s = app.state.settings
    s.push_enabled = True
    s.push_professor_email = "prof@test.ac.kr"
    s.push_contact_email = "admin@test.ac.kr"
    return s


def test_push_restricted_and_minimal_payload_and_logout(app, clients, monkeypatch):
    settings = enable(app)
    p, s = clients["prof"], clients["s1"]
    body = subscription()
    path = "/api/admin/push-subscription"
    assert s.post(path, json=body).status_code == 403
    assert clients["admin"].post(path, json=subscription("admin-device")).status_code == 200
    assert p.post(path, json=body).status_code == 200
    assert p.post(path, json=body).status_code == 200
    slot = make_slots(p)[0]
    assert s.post("/api/bookings", json={"slot_id": slot, "applicant_name": "PRIVATE-NAME",
                                       "topic": "PRIVATE-TOPIC"}).status_code == 201
    with app.state.SessionLocal() as db:
        rows = list(db.scalars(select(Notification)))
        assert len(rows) == 1 and rows[0].channel == "push"
        assert "PRIVATE" not in str(rows[0].payload)
    sent = Mock(return_value=Mock(status_code=201))
    monkeypatch.setattr("pywebpush.webpush", sent)
    assert deliver_one(app.state.SessionLocal, PushSender(settings, app.state.SessionLocal), settings, channel="push")
    data = json.loads(sent.call_args.kwargs["data"])
    assert "PRIVATE" not in str(data) and data["url"] == "/#/bookings"
    p.post("/auth/logout")
    with app.state.SessionLocal() as db:
        remaining = db.scalars(select(PushSubscription)).all()
        assert len(remaining) == 1 and remaining[0].subscription["endpoint"].endswith("/admin-device")


@pytest.mark.parametrize("url", ["http://fcm.googleapis.com/fcm/send/x", "https://127.0.0.1/fcm/send/x",
    "https://fcm.googleapis.com.evil.test/fcm/send/x", "https://user@fcm.googleapis.com/fcm/send/x",
    "https://fcm.googleapis.com:444/fcm/send/x", "https://fcm.googleapis.com/other/x"])
def test_push_rejects_arbitrary_destinations(app, clients, url):
    enable(app)
    body = subscription()
    body["endpoint"] = url
    assert clients["prof"].post("/api/admin/push-subscription", json=body).status_code == 400


@pytest.mark.parametrize("revoke", ["logout", "expired", "role"])
def test_pending_push_is_skipped_after_access_revoked(app, clients, revoke):
    settings = enable(app)
    p = clients["prof"]
    p.post("/api/admin/push-subscription", json=subscription())
    clients["s1"].post("/api/bookings", json={"slot_id": make_slots(p)[0]})
    if revoke == "logout":
        p.post("/auth/logout")
    elif revoke == "role":
        clients["admin"].put(f"/api/admin/users/{p.me['id']}/role", json={"role": "student"})
    else:
        with app.state.SessionLocal() as db:
            for sess in db.scalars(select(AuthSession).where(AuthSession.user_id == p.me["id"])):
                sess.expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
    deliver_one(app.state.SessionLocal, PushSender(settings, app.state.SessionLocal), settings, channel="push")
    with app.state.SessionLocal() as db:
        assert db.scalar(select(Notification)).status == "skipped"


def test_gmail_reauth_does_not_block_push_and_unknown_not_retried(app, clients):
    from tests.integration.test_notifications import enable as enable_mail
    settings = enable(app)
    enable_mail(app)
    p = clients["prof"]
    p.post("/api/admin/push-subscription", json=subscription())
    clients["s1"].post("/api/bookings", json={"slot_id": make_slots(p)[0]})
    gmail = Mock()
    gmail.send.side_effect = MailFailure("reauth", "token_rejected")
    deliver_one(app.state.SessionLocal, gmail, settings)
    push = Mock()
    push.send.side_effect = MailFailure("uncertain", "push_delivery_unknown")
    assert deliver_one(app.state.SessionLocal, push, settings, channel="push")
    assert not deliver_one(app.state.SessionLocal, push, settings, channel="push")
    assert push.send.call_count == 1


def test_real_webpush_encryption_with_mock_http(app, clients, monkeypatch):
    import requests

    from app.infra.push import NoRedirectSession, validate_keys
    settings = enable(app)
    key = ec.generate_private_key(ec.SECP256R1())
    settings.push_private_key = base64.urlsafe_b64encode(
        key.private_numbers().private_value.to_bytes(32, "big")).decode().rstrip("=")
    settings.push_public_key = base64.urlsafe_b64encode(key.public_key().public_bytes(
        Encoding.X962, PublicFormat.UncompressedPoint)).decode().rstrip("=")
    validate_keys(settings.push_public_key, settings.push_private_key)
    p = clients["prof"]
    p.post("/api/admin/push-subscription", json=subscription())
    clients["s1"].post("/api/bookings", json={"slot_id": make_slots(p)[0]})
    calls = []
    def fake_request(self, method, url, **kwargs):
        calls.append(kwargs)
        response = requests.Response()
        response.status_code = 201
        return response
    monkeypatch.setattr(requests.Session, "request", fake_request)
    deliver_one(app.state.SessionLocal, PushSender(settings, app.state.SessionLocal), settings, channel="push")
    assert len(calls) == 1
    assert calls[0]["allow_redirects"] is False
    assert calls[0]["headers"]["content-encoding"] == "aes128gcm"
    assert b"ClassBridge" not in calls[0]["data"]
    with app.state.SessionLocal() as db:
        assert db.scalar(select(Notification)).status == "sent"
    assert issubclass(NoRedirectSession, requests.Session)
