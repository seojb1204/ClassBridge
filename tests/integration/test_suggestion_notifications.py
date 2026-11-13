from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.infra.gmail import message_for
from app.models import Notification, Suggestion, User
from app.models.inbox import InboxNotification
from app.services import suggestion_notifications, suggestion_service
from tests.conftest import PROF

NOW = datetime(2026, 11, 13, 1, 2, 43, tzinfo=timezone.utc)


def enable(app):
    s = app.state.settings
    s.gmail_notifications_enabled = True
    s.gmail_sender_email = "sender@example.com"
    s.gmail_professor_email = PROF


def test_anonymous_notices_without_content_or_identity(app, clients):
    enable(app)
    with app.state.SessionLocal() as db:
        for text in ["private first", "private second"]:
            suggestion_service.save(db, "other", text, False, NOW)
        row = db.scalar(select(Notification))
        assert db.scalar(select(func.count()).select_from(Notification)) == 2
        assert db.scalar(select(func.count()).select_from(Suggestion)) == 2
        assert row.payload == {"kind": "suggestion", "url": app.state.settings.base_url + "/#/suggestions"}
        assert row.booking_id == 0
        assert row.created_at.hour == 15 and row.created_at.minute == 0 and row.created_at.second == 0
        assert row.next_attempt_at == NOW
        inbox_rows = list(db.scalars(select(InboxNotification)))
        assert len(inbox_rows) == 4
        assert {r.available_at for r in inbox_rows} == {r.next_attempt_at for r in db.scalars(select(Notification))}
        assert row.recipient == PROF
        assert row.status == "pending"
        text = message_for(row).as_string()
        assert "private" not in text
        assert message_for(row).get_body().get_content().startswith("새 건의가 접수되었습니다")
        for sid in db.scalars(select(Suggestion.id)):
            assert sid not in row.event_key and sid not in str(row.payload)


def test_notice_failure_rolls_back_submission(app, clients, monkeypatch):
    enable(app)
    def fail(*args):
        raise RuntimeError("synthetic outbox failure")
    monkeypatch.setattr(suggestion_notifications, "enqueue", fail)
    with app.state.SessionLocal() as db:
        with pytest.raises(RuntimeError):
            suggestion_service.save(db, "other", "private", False, NOW)
        db.rollback()
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Suggestion)) == 0
        assert db.scalar(select(func.count()).select_from(Notification)) == 0


def test_no_notice_to_nonprofessor_or_paused_email(app, clients):
    enable(app)
    with app.state.SessionLocal() as db:
        professor = db.scalar(select(User).where(User.email == PROF))
        professor.role = "admin"
        db.commit()
        suggestion_service.save(db, "other", "private", False, NOW)
        assert db.scalar(select(func.count()).select_from(Notification)) == 0


@pytest.mark.parametrize("revoke", [False, True])
def test_suggestion_push_is_generic_and_rechecks_professor(app, clients, monkeypatch, revoke):
    import json
    from unittest.mock import Mock

    from app.db import utcnow
    from app.infra.push import PushSender
    from app.services.notifications import deliver_one
    from tests.integration.test_push import enable as enable_push
    from tests.integration.test_push import subscription

    settings = enable_push(app)
    clients["prof"].post("/api/admin/push-subscription", json=subscription())
    clients["admin"].post("/api/admin/push-subscription", json=subscription("admin"))
    with app.state.SessionLocal() as db:
        suggestion_service.save(db, "other", "private author text", False, utcnow())
        rows = list(db.scalars(select(Notification)))
        assert len(rows) == 1 and rows[0].recipient == PROF
        rows[0].next_attempt_at = utcnow()
        if revoke:
            db.scalar(select(User).where(User.email == PROF)).role = "admin"
        db.commit()
    send = Mock(return_value=Mock(status_code=201))
    monkeypatch.setattr("pywebpush.webpush", send)
    assert deliver_one(app.state.SessionLocal, PushSender(settings, app.state.SessionLocal), settings, channel="push")
    if revoke:
        send.assert_not_called()
    else:
        data = json.loads(send.call_args.kwargs["data"])
        assert data["url"] == "/#/suggestions"
        assert "private" not in str(data)
        assert "새 건의" in data["body"]
    with app.state.SessionLocal() as db:
        assert db.scalar(select(Notification)).status == ("skipped" if revoke else "sent")


def test_suggestion_email_rechecks_professor_before_network(app, clients):
    from unittest.mock import Mock

    from app.db import utcnow
    from app.services.notifications import deliver_one

    enable(app)
    with app.state.SessionLocal() as db:
        suggestion_service.save(db, "other", "private", False, utcnow())
        row = db.scalar(select(Notification))
        row.next_attempt_at = utcnow()
        db.scalar(select(User).where(User.email == PROF)).role = "student"
        db.commit()
    sender = Mock()
    assert deliver_one(app.state.SessionLocal, sender, app.state.settings)
    sender.send.assert_not_called()
    with app.state.SessionLocal() as db:
        assert db.scalar(select(Notification)).status == "skipped"


def test_uncertain_suggestion_does_not_block_next(app, clients):
    from unittest.mock import Mock

    from app.db import utcnow
    from app.services.notifications import deliver_one

    enable(app)
    with app.state.SessionLocal() as db:
        for _ in range(2):
            suggestion_service.save(db, "other", "private", False, utcnow())
        rows = list(db.scalars(select(Notification).order_by(Notification.id)))
        rows[1].chain_id = rows[0].chain_id  # Even an identifier collision cannot block independent notices.
        rows[0].status = "uncertain"
        rows[1].next_attempt_at = utcnow()
        db.commit()
    sender = Mock()
    sender.send.return_value = "mock accepted"
    assert deliver_one(app.state.SessionLocal, sender, app.state.settings)
    assert sender.send.call_count == 1


def test_immediate_new_notice_preserves_legacy_delayed_queue(app, clients, monkeypatch):
    from datetime import timedelta
    from unittest.mock import Mock

    from app.services.notifications import deliver_one

    enable(app)
    legacy_due = NOW + timedelta(minutes=7)
    with app.state.SessionLocal() as db:
        suggestion_service.save(db, "other", "legacy synthetic", False, NOW)
        old = db.scalar(select(Notification))
        old.next_attempt_at = legacy_due
        for row in db.scalars(select(InboxNotification)):
            row.available_at = legacy_due
        db.commit()
        old_id = old.id
        suggestion_service.save(db, "other", "new synthetic", False, NOW)
        assert db.scalar(select(func.count()).select_from(Notification)) == 2
        assert db.get(Notification, old_id).next_attempt_at == legacy_due
    monkeypatch.setattr('app.services.notifications.utcnow', lambda: NOW)
    sender = Mock()
    sender.send.return_value = "synthetic accepted"
    assert deliver_one(app.state.SessionLocal, sender, app.state.settings)
    assert sender.send.call_count == 1
    assert not deliver_one(app.state.SessionLocal, sender, app.state.settings)
    with app.state.SessionLocal() as db:
        assert db.get(Notification, old_id).status == "pending"
        assert db.get(Notification, old_id).next_attempt_at == legacy_due
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.status == "sent")) == 1
    monkeypatch.setattr('app.services.notifications.utcnow', lambda: legacy_due)
    assert deliver_one(app.state.SessionLocal, sender, app.state.settings)
    assert sender.send.call_count == 2
    assert not deliver_one(app.state.SessionLocal, sender, app.state.settings)
    with app.state.SessionLocal() as db:
        assert db.get(Notification, old_id).status == "sent"


def test_paused_email_stays_paused_with_immediate_inbox(app, clients):
    from app.models import AppSetting
    from app.services.personal_alerts import EMAIL_PAUSED

    enable(app)
    with app.state.SessionLocal() as db:
        db.add(AppSetting(key=EMAIL_PAUSED, value=True))
        db.commit()
        suggestion_service.save(db, "other", "synthetic private", False, NOW)
        assert db.get(AppSetting, EMAIL_PAUSED).value is True
        assert db.scalar(select(func.count()).select_from(Notification)) == 0
        assert all(row.available_at == NOW for row in db.scalars(select(InboxNotification)))
        assert db.scalar(select(func.count()).select_from(InboxNotification)) == 2
