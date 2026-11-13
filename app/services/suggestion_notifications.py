"""Anonymous, immediately eligible suggestion notices. Never retain a suggestion reference."""
import uuid
from datetime import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import Notification, User
from app.services import inbox
from app.services.personal_alerts import devices, email_paused, preferences
from app.timeutil import kst_date, kst_to_utc


def enqueue(db, now):
    day = kst_date(now)
    bucket = kst_to_utc(day, time.min)
    due = now
    key = uuid.uuid4().hex
    # No suggestion/author link; notification timing can reveal the submission time.
    inbox.enqueue(db, f"suggestion-{key}", "suggestion", available_at=due)
    settings = db.info.get("settings")
    if not settings or not (settings.gmail_notifications_enabled or settings.push_enabled):
        return
    payload = {"kind": "suggestion", "url": settings.base_url + "/#/suggestions"}
    recipients = []
    if settings.gmail_notifications_enabled and not email_paused(db):
        professor = db.scalar(select(User).where(User.email == settings.gmail_professor_email,
                                                User.role == "professor", User.is_active.is_(True)))
        if professor:
            recipients.append(("gmail", professor.email, None, settings.gmail_sender_email, professor.id))
    if settings.push_enabled:
        for device, user in db.execute(devices(now).where(User.role == "professor")):
            if preferences(user).instant:
                recipients.append(("push", user.email, device.id, "", device.id))
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    for channel, recipient, subscription_id, sender, target in recipients:
        db.execute(insert(Notification).values(
            event_key=f"suggestion-batch-{key}-{channel}-{target}", chain_id=-int(key[:7], 16),
            booking_id=0, payload=payload, sender=sender, recipient=recipient,
            channel=channel, subscription_id=subscription_id, created_at=bucket, next_attempt_at=due,
        ).on_conflict_do_nothing(index_elements=[Notification.event_key]))
