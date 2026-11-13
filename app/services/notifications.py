"""Transactional outbox with short DB claims; network calls never hold a DB lock."""
import logging
from datetime import timedelta
from threading import Event, Thread

from sqlalchemy import exists, or_, select, update
from sqlalchemy.orm import aliased

from app.db import utcnow
from app.infra.gmail import GmailSender, MailFailure
from app.models import Booking, Slot, User
from app.models.notification import Notification
from app.services.personal_alerts import daily_due, devices, email_paused, enqueue_due, preferences
from app.services.staff_reminders import enqueue_due as enqueue_staff_due
from app.services.staff_reminders import next_due as next_staff_due

log = logging.getLogger("classbridge.notifications")


def enqueue(db, booking, event, kind, *, old=None):
    from app.services.inbox import enqueue as enqueue_inbox
    enqueue_inbox(db, f"booking-event-{event.id}", kind)
    settings = db.info.get("settings")
    if not settings or not (settings.gmail_notifications_enabled or settings.push_enabled):
        return
    payload = {"kind": kind, "student_name": booking.applicant_name,
               "start": booking.slot.start_at.isoformat(), "end": booking.slot.end_at.isoformat(),
               "url": settings.base_url + "/#/bookings"}
    if not payload["student_name"]:
        payload["student_name"] = db.get(User, booking.student_id).name
    previous = db.scalar(select(Notification).where(Notification.booking_id == (old.id if old else booking.id))
                         .order_by(Notification.id.desc()).limit(1))
    chain = previous.chain_id if previous else (old.id if old else booking.id)
    if old:
        payload.update(old_id=old.id, old_start=old.slot.start_at.isoformat(), old_end=old.slot.end_at.isoformat())
    if settings.gmail_notifications_enabled and not email_paused(db):
        db.add(Notification(event_key=f"booking-event-{event.id}", chain_id=chain,
                            booking_id=booking.id, payload=payload,
                            sender=settings.gmail_sender_email, recipient=settings.gmail_professor_email))
    if settings.push_enabled:
        subscriptions = db.execute(devices(utcnow()))
        minimal = {k: v for k, v in payload.items() if k != "student_name"}
        for sub, user in subscriptions:
            if not preferences(user).instant:
                continue
            db.add(Notification(event_key=f"booking-event-{event.id}-push-{sub.id}", chain_id=chain,
                booking_id=booking.id, payload=minimal, sender="", recipient=user.email,
                channel="push", subscription_id=sub.id))


def claim(session_factory, now=None, channel="gmail"):
    now = now or utcnow()
    with session_factory() as db:
        if channel == 'gmail' and email_paused(db):
            return None
        # Never blindly resend an abandoned delivery: Gmail may already have accepted it.
        db.execute(update(Notification).where(Notification.status == "sending", Notification.lease_until < now)
                   .values(status="uncertain", error_code="delivery_interrupted", lease_until=None))
        if db.scalar(select(Notification.id).where(Notification.status == "reauth",
                     Notification.channel == channel).limit(1)):
            db.commit()
            return None
        earlier = aliased(Notification)
        blocked = exists(select(earlier.id).where(earlier.chain_id == Notification.chain_id,
                         earlier.channel == Notification.channel, earlier.recipient == Notification.recipient,
                         earlier.subscription_id.is_not_distinct_from(Notification.subscription_id),
                         earlier.id < Notification.id, earlier.status.not_in(("sent", "skipped"))))
        row = db.scalar(select(Notification).where(Notification.status == "pending", Notification.channel == channel,
                        Notification.next_attempt_at <= now,
                        or_(Notification.payload["kind"].as_string().in_(("suggestion", "custom_reminder")), ~blocked))
                        .order_by(Notification.id).limit(1).with_for_update(skip_locked=True))
        if row is None:
            db.commit()
            return None
        # CAS also prevents duplicate ownership in SQLite where FOR UPDATE is ignored.
        changed = db.execute(update(Notification).where(Notification.id == row.id, Notification.status == "pending")
                             .values(status="sending", attempts=Notification.attempts + 1,
                                     lease_until=now + timedelta(minutes=3)))
        if changed.rowcount != 1:
            db.rollback()
            return None
        db.commit()
        db.refresh(row)
        db.expunge(row)
        return row


def deliver_one(session_factory, sender, settings, now=None, channel="gmail"):
    if not (settings.gmail_notifications_enabled if channel == "gmail" else settings.push_enabled):
        return False
    row = claim(session_factory, now, channel)
    if row is None:
        return False
    now = now or utcnow()
    values = {"lease_until": None}
    try:
        if channel == "gmail" and row.payload.get("kind") == "suggestion":
            with session_factory() as db:
                permitted = db.scalar(select(User.id).where(User.email == row.recipient,
                    User.role == "professor", User.is_active.is_(True)))
                if not permitted or email_paused(db):
                    raise MailFailure("skipped", "recipient_permission_revoked")
        gmail_id = sender.send(row)
        values.update(status="sent", sent_at=utcnow(), gmail_id=gmail_id, error_code="")
    except MailFailure as exc:
        state = "failed" if exc.state == "pending" and row.attempts >= 8 else exc.state
        values.update(status=state, error_code=exc.code,
                      next_attempt_at=now + timedelta(seconds=min(3600, 30 * 2 ** min(row.attempts, 7))))
    except Exception:
        # Exception text might contain bearer tokens or message bodies: never log it.
        values.update(status="uncertain", error_code="delivery_unknown")
    with session_factory() as db:
        db.execute(update(Notification).where(Notification.id == row.id, Notification.status == "sending",
                    Notification.attempts == row.attempts).values(**values))
        db.commit()
    return True


def next_worker_delay(session_factory, settings, now):
    """Plan the next real outbox retry/reminder without idle DB polling.

    All app writes signal the local worker. Six-hour reconciliation handles
    out-of-band edits; the application supports a single server instance.
    """
    due_times = []
    with session_factory() as db:
        staff_due = next_staff_due(db)
        if staff_due:
            due_times.append(staff_due)
        channels = []
        if settings.gmail_notifications_enabled and not email_paused(db):
            channels.append("gmail")
        if settings.push_enabled:
            channels.append("push")
        for channel in channels:
            # A paused/reauth/blocked chain must not cause a busy loop.
            if db.scalar(select(Notification.id).where(Notification.status == "reauth",
                         Notification.channel == channel).limit(1)):
                continue
            earlier = aliased(Notification)
            blocked = exists(select(earlier.id).where(earlier.chain_id == Notification.chain_id,
                earlier.channel == Notification.channel, earlier.recipient == Notification.recipient,
                earlier.subscription_id.is_not_distinct_from(Notification.subscription_id),
                earlier.id < Notification.id, earlier.status.not_in(("sent", "skipped"))))
            pending = db.scalar(select(Notification.next_attempt_at).where(
                Notification.status == "pending", Notification.channel == channel,
                or_(Notification.payload["kind"].as_string().in_(("suggestion", "custom_reminder")), ~blocked))
                .order_by(Notification.next_attempt_at).limit(1))
            if pending:
                due_times.append(pending)
        leases = db.scalars(select(Notification.lease_until).where(
            Notification.status == "sending", Notification.channel.in_(channels),
            Notification.lease_until.is_not(None))).all()
        due_times.extend(leases)
        if settings.push_enabled:
            active = list(db.execute(devices(now)))
            for _, user in active:
                pref = preferences(user)
                if pref.daily:
                    for offset in range(8):
                        due = daily_due(pref, now + timedelta(days=offset))
                        if due and due > now:
                            due_times.append(due)
                            break
            if any(preferences(user).reminder for _, user in active):
                upcoming = db.scalars(select(Slot.start_at).join(Booking, Booking.slot_id == Slot.id)
                    .where(Booking.status == "booked", Slot.status == "open",
                           Slot.start_at > now + timedelta(minutes=30))).all()
                due_times.extend(start - timedelta(minutes=30) for start in upcoming)
    return min(21600, max(0.1, (min(due_times) - now).total_seconds())) if due_times else 21600


class NotificationWorker:
    def __init__(self, session_factory, settings):
        self.session_factory, self.settings = session_factory, settings
        self.stop_event = Event()
        self.wake_event = Event()
        self.thread = Thread(target=self.run, name="gmail-outbox", daemon=True)

    def run(self):
        from app.infra.push import PushSender
        sender = GmailSender(self.settings)
        push_sender = PushSender(self.settings, self.session_factory)
        try:
            while not self.stop_event.is_set():
                self.wake_event.clear()
                delay = 20  # Retry transient failures inside the three-minute alert grace.
                try:
                    scanned_at = utcnow()
                    with self.session_factory() as db:
                        enqueue_staff_due(db, scanned_at)
                        if self.settings.push_enabled:
                            enqueue_due(db, scanned_at)
                    did_work = deliver_one(self.session_factory, sender, self.settings)
                    did_work = deliver_one(self.session_factory, push_sender, self.settings, channel="push") or did_work
                    delay = 0 if did_work else next_worker_delay(self.session_factory, self.settings, scanned_at)
                    delay = max(0, delay - (utcnow() - scanned_at).total_seconds())
                except Exception:
                    log.error("notification worker unavailable; pending records retained")
                self.wake_event.wait(delay)
        finally:
            sender.close()

    def start(self):
        self.thread.start()

    def wake(self):
        self.wake_event.set()

    def stop(self):
        self.stop_event.set()
        self.wake_event.set()
        self.thread.join(timeout=35)
