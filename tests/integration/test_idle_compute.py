"""Idle workers must not keep Neon awake; scheduled work still runs on time."""
import asyncio
from datetime import datetime, timedelta
from threading import Event
from unittest.mock import Mock

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.db import utcnow
from app.models import AuthSession, Booking, Notification, PushSubscription, Slot, User
from app.services import auto_complete
from app.services.notifications import next_worker_delay
from app.timeutil import KST
from tests.conftest import make_slots
from tests.integration.test_notifications import enable as enable_mail
from tests.integration.test_push import enable as enable_push
from tests.integration.test_push import subscription


def test_health_does_not_touch_database_but_readiness_does(app):
    queries = []
    event.listen(app.state.engine, "before_cursor_execute", lambda *args: queries.append(args[2]))
    client = TestClient(app)
    for _ in range(5):
        assert client.get("/healthz").json() == {"status": "ok"}
    assert queries == []
    assert client.get("/readyz").status_code == 200
    assert queries == ["SELECT 1"]


def test_only_writes_wake_workers(app):
    app.state.completion_wake = Event()
    app.state.notification_worker = Mock()
    client = TestClient(app)
    client.get("/healthz")
    assert not app.state.completion_wake.is_set()
    app.state.notification_worker.wake.assert_not_called()
    client.post("/no-such-route")
    assert app.state.completion_wake.is_set()
    app.state.notification_worker.wake.assert_called_once()


def test_completion_plans_actual_next_end(app, clients):
    factory = app.state.SessionLocal
    now = utcnow()
    assert auto_complete.next_delay(factory, now) == 21600
    sid = make_slots(clients["prof"])[0]
    bid = clients["s1"].post("/api/bookings", json={"slot_id": sid}).json()["id"]
    with factory.begin() as db:
        slot = db.get(Slot, sid)
        slot.start_at, slot.end_at = now - timedelta(minutes=20), now + timedelta(seconds=41)
    assert auto_complete.next_delay(factory, now) == 41
    with factory.begin() as db:
        db.get(Booking, bid).status = "cancelled"
    assert auto_complete.next_delay(factory, now) == 21600


def test_completion_waits_until_signal_and_stops_immediately(monkeypatch):
    calls = []
    monkeypatch.setattr(auto_complete, "complete_elapsed", lambda *a: calls.append(1))
    monkeypatch.setattr(auto_complete, "next_delay", lambda *a: 21600)
    async def scenario():
        stop, wake = asyncio.Event(), asyncio.Event()
        task = asyncio.create_task(auto_complete.run(None, stop, wake))
        for _ in range(100):
            if calls:
                break
            await asyncio.sleep(.01)
        assert len(calls) == 1
        await asyncio.sleep(.05)
        assert len(calls) == 1
        wake.set()
        for _ in range(100):
            if len(calls) == 2:
                break
            await asyncio.sleep(.01)
        assert len(calls) == 2
        stop.set()
        await asyncio.wait_for(task, 1)
    asyncio.run(scenario())


def test_outbox_idle_retry_and_blocked_chains(app, clients):
    settings = enable_mail(app)
    factory = app.state.SessionLocal
    now = utcnow()
    assert next_worker_delay(factory, settings, now) == 21600
    sid = make_slots(clients["prof"])[0]
    bid = clients["s1"].post("/api/bookings", json={"slot_id": sid}).json()["id"]
    clients["s1"].post(f"/api/bookings/{bid}/cancel", json={})
    with factory.begin() as db:
        rows = list(db.scalars(select(Notification).order_by(Notification.id)))
        rows[0].next_attempt_at = now + timedelta(seconds=67)
    assert next_worker_delay(factory, settings, now) == 67
    with factory.begin() as db:
        rows = list(db.scalars(select(Notification).order_by(Notification.id)))
        rows[0].status = "uncertain"
    assert next_worker_delay(factory, settings, now) == 21600


def test_push_plans_daily_and_thirty_minute_reminders(app, clients):
    enable_push(app)
    settings, factory = app.state.settings, app.state.SessionLocal
    p = clients["prof"]
    now = datetime(2026, 1, 5, 9, 50, tzinfo=KST)
    p.post("/api/admin/push-subscription", json=subscription())
    sid = make_slots(p)[0]
    clients["s1"].post("/api/bookings", json={"slot_id": sid})
    with factory.begin() as db:
        sub = db.scalar(select(PushSubscription))
        db.get(AuthSession, sub.session_id).expires_at = now + timedelta(days=7)
        # Existing immediate jobs have already been delivered.
        for row in db.scalars(select(Notification)):
            row.status = "sent"
        slot = db.get(Slot, sid)
        slot.start_at, slot.end_at = now + timedelta(minutes=35), now + timedelta(hours=1)
    assert next_worker_delay(factory, settings, now) == 600  # 10:00 daily
    with factory.begin() as db:
        db.get(User, p.me["id"]).alert_preferences = {"reminder": True}
    assert next_worker_delay(factory, settings, now) == 300  # 09:55 reminder


def test_paused_mail_does_not_spin_on_expired_lease(app, clients):
    from app.models import AppSetting
    from app.services.personal_alerts import EMAIL_PAUSED
    settings = enable_mail(app)
    sid = make_slots(clients["prof"])[0]
    clients["s1"].post("/api/bookings", json={"slot_id": sid})
    now = utcnow()
    with app.state.SessionLocal.begin() as db:
        row = db.scalar(select(Notification))
        row.status, row.lease_until = "sending", now - timedelta(minutes=1)
        db.add(AppSetting(key=EMAIL_PAUSED, value="true"))
    assert next_worker_delay(app.state.SessionLocal, settings, now) == 21600


def test_completion_runs_at_due_timeout_without_foreground_request(monkeypatch):
    calls = []
    monkeypatch.setattr(auto_complete, "complete_elapsed", lambda *a: calls.append(1))
    monkeypatch.setattr(auto_complete, "next_delay", lambda *a: .02)
    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(auto_complete.run(None, stop))
        for _ in range(100):
            if len(calls) >= 2:
                break
            await asyncio.sleep(.01)
        assert len(calls) >= 2
        stop.set()
        await asyncio.wait_for(task, 1)
    asyncio.run(scenario())


def test_completion_uses_same_scan_clock_across_end_boundary(monkeypatch):
    baseline = utcnow()
    clock = iter([baseline, baseline, baseline + timedelta(seconds=2)])
    monkeypatch.setattr(auto_complete, "utcnow", lambda: next(clock))
    seen = []
    monkeypatch.setattr(auto_complete, "complete_elapsed", lambda f, s, n: seen.append(n))
    async def scenario():
        stop = asyncio.Event()
        def plan(factory, now):
            assert now == seen[0] == baseline
            stop.set()
            return 1
        monkeypatch.setattr(auto_complete, "next_delay", plan)
        await auto_complete.run(None, stop)
    asyncio.run(scenario())


def test_notification_scan_clock_and_fast_failure_retry(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from app.services import notifications
    baseline = utcnow()
    settings = SimpleNamespace(push_enabled=True)
    sender = Mock()
    monkeypatch.setattr(notifications, "GmailSender", lambda s: sender)
    monkeypatch.setattr("app.infra.push.PushSender", lambda *args: Mock())
    monkeypatch.setattr(notifications, "deliver_one", lambda *args, **kwargs: False)
    seen = []
    monkeypatch.setattr(notifications, "enqueue_due", lambda db, now: seen.append(now))
    monkeypatch.setattr(notifications, "enqueue_staff_due", lambda db, now: None)
    def plan(factory, settings, now):
        assert now == seen[0] == baseline
        return 1
    monkeypatch.setattr(notifications, "next_worker_delay", plan)
    clock = iter([baseline, baseline + timedelta(seconds=2)])
    monkeypatch.setattr(notifications, "utcnow", lambda: next(clock))
    worker = notifications.NotificationWorker(lambda: nullcontext(None), settings)
    worker.wake_event = Mock()
    worker.wake_event.wait.side_effect = lambda delay: worker.stop_event.set()
    worker.run()
    worker.wake_event.wait.assert_called_once_with(0)
    # A brief outage must not delay retry beyond the 3-minute push grace.
    worker = notifications.NotificationWorker(lambda: nullcontext(None), settings)
    worker.wake_event = Mock()
    worker.wake_event.wait.side_effect = lambda delay: worker.stop_event.set()
    monkeypatch.setattr(notifications, "utcnow", lambda: baseline)
    def fail(db, now):
        raise RuntimeError("temporary database outage")
    monkeypatch.setattr(notifications, "enqueue_due", fail)
    worker.run()
    worker.wake_event.wait.assert_called_once_with(20)
