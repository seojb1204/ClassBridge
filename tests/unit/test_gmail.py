import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import ConfigError, Settings
from app.infra.gmail import SCOPE, GmailSender, MailFailure


def settings():
    return Settings(gmail_notifications_enabled=True, gmail_client_id="sender-client",
                    gmail_client_secret="SECRET", gmail_refresh_token="REFRESH",
                    gmail_sender_email="sender@example.com", gmail_professor_email="professor@example.com")


def row():
    return SimpleNamespace(sender="sender@example.com", recipient="professor@example.com", booking_id=123,
                           event_key="booking-event-5", payload={"kind": "created", "student_name": "학생 이름",
                           "start": "2026-11-10T01:00:00+00:00", "end": "2026-11-10T01:30:00+00:00",
                           "url": "https://classbridge-staging.onrender.com/#/bookings"})


def test_refresh_cache_sender_scope_and_minimal_message():
    calls = []
    def handle(req):
        calls.append(req)
        if req.url.host == "oauth2.googleapis.com":
            assert b"refresh_token=REFRESH" in req.content
            assert b"client_id=sender-client" in req.content
            return httpx.Response(200, json={"access_token": "ACCESS", "expires_in": 3600, "scope": SCOPE})
        assert req.headers["Authorization"] == "Bearer ACCESS"
        assert "sender%40example.com" in str(req.url)
        raw = base64.urlsafe_b64decode(json.loads(req.content)["raw"])
        assert b"To: professor@example.com" in raw
        return httpx.Response(200, json={"id": "abc123"})
    sender = GmailSender(settings(), httpx.MockTransport(handle))
    assert sender.send(row()) == "abc123"
    assert sender.send(row()) == "abc123"
    assert len(calls) == 3
    sender.close()


@pytest.mark.parametrize("response,state", [(400, "reauth"), (429, "pending"), (503, "pending")])
def test_refresh_rejection_never_sends(response, state):
    calls = []
    def handle(req):
        calls.append(req)
        return httpx.Response(response, json={"error": "invalid_grant", "secret": "DO-NOT-LEAK"})
    sender = GmailSender(settings(), httpx.MockTransport(handle))
    with pytest.raises(MailFailure) as exc:
        sender.send(row())
    assert exc.value.state == state and "DO-NOT-LEAK" not in str(exc.value)
    assert len(calls) == 1
    sender.close()


@pytest.mark.parametrize("scope", ["", SCOPE + " https://mail.google.com/", "openid"])
def test_scope_must_be_attested_and_send_only(scope):
    sender = GmailSender(settings(), httpx.MockTransport(lambda req: httpx.Response(200,
        json={"access_token": "ACCESS", "expires_in": 3600, "scope": scope})))
    with pytest.raises(MailFailure, match="scope_unverified"):
        sender.send(row())
    sender.close()


@pytest.mark.parametrize("code,state", [(429, "pending"), (500, "uncertain"), (403, "reauth"), (400, "failed")])
def test_send_errors(code, state):
    def handle(req):
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ACCESS", "expires_in": 3600, "scope": SCOPE})
        return httpx.Response(code, json={"error": "PRIVATE-BODY"})
    sender = GmailSender(settings(), httpx.MockTransport(handle))
    with pytest.raises(MailFailure) as exc:
        sender.send(row())
    assert exc.value.state == state and "PRIVATE-BODY" not in str(exc.value)
    sender.close()


def test_timeout_after_send_is_uncertain():
    def handle(req):
        if req.url.host == "oauth2.googleapis.com":
            return httpx.Response(200, json={"access_token": "ACCESS", "expires_in": 3600, "scope": SCOPE})
        raise httpx.ReadTimeout("SECRET payload", request=req)
    sender = GmailSender(settings(), httpx.MockTransport(handle))
    with pytest.raises(MailFailure) as exc:
        sender.send(row())
    assert exc.value.state == "uncertain" and "SECRET" not in str(exc.value)
    sender.close()


def test_recipient_change_cannot_redirect_existing_mail():
    s = settings()
    s.gmail_professor_email = "different@example.com"
    sender = GmailSender(s, httpx.MockTransport(lambda req: pytest.fail("must not call Gmail")))
    with pytest.raises(MailFailure, match="recipient_config_changed"):
        sender.send(row())
    sender.close()


def test_configuration_separation_and_header_injection():
    s = settings()
    s.validate()
    assert "REFRESH" not in repr(s) and "SECRET" not in repr(s)
    s.google_client_id = s.gmail_client_id
    with pytest.raises(ConfigError):
        s.validate()
    s.google_client_id = "login-client"
    s.gmail_professor_email = "prof@example.com\r\nBcc: other@example.com"
    with pytest.raises(ConfigError):
        s.validate()
