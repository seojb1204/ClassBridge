from datetime import datetime, timedelta

from sqlalchemy import select

from app.models import Notification, Slot, User
from app.services.personal_alerts import enqueue_due, preferences, scheduled_message
from app.timeutil import KST
from tests.conftest import make_slots
from tests.integration.test_push import enable, subscription


def test_personal_alerts_access_and_defaults(app, clients):
    enable(app)
    path = "/api/admin/personal-alerts"
    p, a, s = (clients[key] for key in ("prof", "admin", "s1"))
    assert s.get(path).status_code == 403
    default = p.get(path).json()
    assert default == {"daily": True, "at": "10:00", "reminder": False, "instant": True, "names": True}
    assert a.get(path).json()["daily"] is False
    assert a.put(path, json={**default, "at": "25:00"}).status_code == 422
    assert a.put(path, json={**default, "at": "09:00"}).status_code == 200
    assert p.get(path).json() == default
    assert p.put("/api/admin/email-delivery", json={"paused": True}).status_code == 403
    assert a.put("/api/admin/email-delivery", json={"paused": True}).status_code == 200
    assert a.get("/api/admin/notifications").json()["email_paused"]


def test_due_schedule_deduplicates_merges_and_rechecks_cancellations(app, clients):
    enable(app)
    p = clients["prof"]
    # Pin the worker clock to a Monday and give the simulated session a matching expiry.
    now = datetime(2026, 1, 5, 10, tzinfo=KST)
    p.post("/api/admin/push-subscription", json=subscription())
    slot = make_slots(p)[0]
    student = clients["s1"]
    booking = student.post("/api/bookings", json={"slot_id": slot, "applicant_name": "테스트학생"}).json()
    path = "/api/admin/personal-alerts"
    p.put(path, json={**p.get(path).json(), "reminder": True})
    with app.state.SessionLocal() as db:
        from app.models import AuthSession, PushSubscription
        sub = db.scalar(select(PushSubscription))
        db.get(AuthSession, sub.session_id).expires_at = now + timedelta(days=7)
        s = db.get(Slot, slot)
        s.start_at, s.end_at = now + timedelta(minutes=30), now + timedelta(hours=1)
        db.commit()
        enqueue_due(db, now)
        enqueue_due(db, now + timedelta(seconds=20))
        jobs = db.scalars(select(Notification).where(Notification.booking_id == 0)).all()
        assert len(jobs) == 1
        pref = preferences(db.get(User, p.me["id"]))
        msg = scheduled_message(db, jobs[0].payload, pref, now)
        assert "오늘 상담 1건" in msg["title"] and "테스트학생" in msg["body"] and "30분 후" in msg["body"]
        pref.names = False
        assert "1명" in scheduled_message(db, jobs[0].payload, pref, now)["body"]
        pref.at = "09:00"
        reminder = {"kind": "reminder", "due": now.isoformat()}
        assert "30분 후 상담" == scheduled_message(db, reminder, pref, now)["title"]
        pref.reminder = False
        assert scheduled_message(db, reminder, pref, now) is None
        assert scheduled_message(db, jobs[0].payload, pref, now) is None
        enqueue_due(db, now + timedelta(days=1))
        assert len(db.scalars(select(Notification).where(Notification.booking_id == 0)).all()) == 1
        # With a different summary time, the same slot is one standalone reminder per device.
        user = db.get(User, p.me["id"])
        pref.reminder = True
        user.alert_preferences = pref.model_dump()
        db.commit()
        enqueue_due(db, now)
        enqueue_due(db, now + timedelta(seconds=10))
        reminder_rows = db.scalars(select(Notification).where(Notification.event_key.like("reminder-%"))).all()
        assert len(reminder_rows) == 1
        assert scheduled_message(db, reminder_rows[0].payload, pref, now)["body"] == "오전 10시 30분 · 1명"
        from app.models import Booking
        db.get(Booking, booking["id"]).status = "cancelled"
        db.commit()
        pref.at = "10:00"
        assert scheduled_message(db, jobs[0].payload, pref, now) is None
