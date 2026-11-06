"""Transactional outbox with short DB claims; network calls never hold a DB lock."""
import logging
from datetime import timedelta
from threading import Event, Thread

from sqlalchemy import exists, select, update
from sqlalchemy.orm import aliased

from app.db import utcnow
from app.infra.gmail import GmailSender, MailFailure
from app.models import AuthSession, User
from app.models.notification import Notification, PushSubscription

log = logging.getLogger("classbridge.notifications")


def enqueue(db, booking, event, kind, *, old=None):
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
    if settings.gmail_notifications_enabled:
        db.add(Notification(event_key=f"booking-event-{event.id}", chain_id=chain,
                            booking_id=booking.id, payload=payload,
                            sender=settings.gmail_sender_email, recipient=settings.gmail_professor_email))
    if settings.push_enabled:
        subscriptions = db.scalars(select(PushSubscription).join(AuthSession).join(User).where(
            User.email == settings.push_professor_email, User.is_active.is_(True),
            User.role.in_(("professor", "admin")), AuthSession.expires_at > utcnow()))
        minimal = {k: v for k, v in payload.items() if k != "student_name"}
        for sub in subscriptions:
            db.add(Notification(event_key=f"booking-event-{event.id}-push-{sub.id}", chain_id=chain,
                booking_id=booking.id, payload=minimal, sender="", recipient=settings.push_professor_email,
                channel="push", subscription_id=sub.id))


def claim(session_factory, now=None, channel="gmail"):
    now = now or utcnow()
    with session_factory() as db:
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
                        Notification.next_attempt_at <= now, ~blocked)
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


class NotificationWorker:
    def __init__(self, session_factory, settings):
        self.session_factory, self.settings = session_factory, settings
        self.stop_event = Event()
        self.thread = Thread(target=self.run, name="gmail-outbox", daemon=True)

    def run(self):
        from app.infra.push import PushSender
        sender = GmailSender(self.settings)
        push_sender = PushSender(self.settings, self.session_factory)
        try:
            while not self.stop_event.is_set():
                try:
                    did_work = deliver_one(self.session_factory, sender, self.settings)
                    did_work = deliver_one(self.session_factory, push_sender, self.settings, channel="push") or did_work
                except Exception:
                    log.error("notification worker unavailable; pending records retained")
                    did_work = False
                self.stop_event.wait(1 if did_work else 60)
        finally:
            sender.close()

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=35)
