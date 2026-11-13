"""Durable scheduling; enqueue and dispatch marker commit as one transaction."""
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.core.errors import BadRequest, Conflict, NotFound
from app.db import utcnow
from app.models import InboxNotification, Notification, User
from app.models.staff_reminder import StaffReminder
from app.repositories import audit
from app.services.personal_alerts import devices, preferences
from app.timeutil import kst_date


def create(db, identifier, recipient_id, message, scheduled_at, actor_id):
    if not isinstance(message, str) or not message.strip() or len(message) > 240:
        raise BadRequest("알림 내용은 1~240자여야 합니다")
    if any(ord(c) < 32 and c not in '\n\t' for c in message):
        raise BadRequest("알림 내용을 확인하세요")
    if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
        raise BadRequest("알림 시간에 시간대를 지정하세요")
    old = db.get(StaffReminder, identifier)
    if old:
        if (old.recipient_id, old.message, old.scheduled_at) != (recipient_id, message, scheduled_at):
            raise Conflict("같은 요청 번호에 다른 알림을 저장할 수 없습니다")
        return old
    if scheduled_at <= utcnow():
        raise BadRequest("미래의 알림 시간을 선택하세요")
    recipient = db.get(User, recipient_id)
    if not recipient or not recipient.is_active or recipient.role != 'professor':
        raise BadRequest("활성 교수자만 알림 대상으로 지정할 수 있습니다")
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    result = db.execute(insert(StaffReminder).values(id=identifier, recipient_id=recipient_id, message=message,
        scheduled_at=scheduled_at, created_by=actor_id).on_conflict_do_nothing(index_elements=[StaffReminder.id]))
    db.flush()
    row = db.get(StaffReminder, identifier)
    if (row.recipient_id, row.message, row.scheduled_at) != (recipient_id, message, scheduled_at):
        raise Conflict("같은 요청 번호에 다른 알림을 저장할 수 없습니다")
    if result.rowcount:
        audit.add(db, actor_id, "staff_reminder.created", "staff_reminder", identifier)
    db.commit()
    return row


def cancel(db, identifier, actor_id=None):
    row = db.scalar(select(StaffReminder).where(StaffReminder.id == identifier).with_for_update())
    if row is None:
        raise NotFound("예약 알림을 찾을 수 없습니다")
    result = db.execute(update(StaffReminder).where(StaffReminder.id == identifier,
        StaffReminder.dispatched_at.is_(None), StaffReminder.cancelled_at.is_(None))
        .values(cancelled_at=utcnow()).execution_options(synchronize_session=False))
    db.refresh(row)
    if row.dispatched_at:
        raise Conflict("이미 발송 처리된 알림은 취소할 수 없습니다")
    if result.rowcount:
        audit.add(db, actor_id, "staff_reminder.cancelled", "staff_reminder", identifier)
    db.commit()
    return row


def next_due(db):
    return db.scalar(select(func.min(StaffReminder.scheduled_at)).where(
        StaffReminder.dispatched_at.is_(None), StaffReminder.cancelled_at.is_(None)))


def enqueue_due(db, now):
    insert = pg_insert if db.get_bind().dialect.name == 'postgresql' else sqlite_insert
    rows = db.scalars(select(StaffReminder).where(StaffReminder.scheduled_at <= now,
        StaffReminder.dispatched_at.is_(None), StaffReminder.cancelled_at.is_(None))
        .order_by(StaffReminder.scheduled_at).limit(100).with_for_update(skip_locked=True))
    settings = db.info.get('settings')
    for row in rows:
        claimed = db.execute(update(StaffReminder).where(StaffReminder.id == row.id,
            StaffReminder.dispatched_at.is_(None), StaffReminder.cancelled_at.is_(None))
            .values(dispatched_at=now).execution_options(synchronize_session=False))
        if not claimed.rowcount:
            continue
        recipient = db.get(User, row.recipient_id)
        if not recipient or not recipient.is_active or recipient.role != 'professor':
            row.cancelled_at = now
            row.dispatched_at = None
            db.execute(update(StaffReminder).where(StaffReminder.id == row.id).values(dispatched_at=None))
            continue
        key = f"staff-reminder-{row.id}"
        db.execute(insert(InboxNotification).values(recipient_id=row.recipient_id, event_key=key,
            kind='custom_reminder', message=row.message, created_on=kst_date(row.scheduled_at),
            available_at=row.scheduled_at).on_conflict_do_nothing(
                index_elements=[InboxNotification.recipient_id, InboxNotification.event_key]))
        if settings and settings.push_enabled:
            for sub, user in db.execute(devices(now).where(User.id == row.recipient_id)):
                if preferences(user).instant:
                    db.execute(insert(Notification).values(event_key=f'{key}-push-{sub.id}', chain_id=0,
                        booking_id=0, payload={'kind': 'custom_reminder', 'reminder_id': row.id},
                        sender='', recipient=user.email, channel='push', subscription_id=sub.id,
                        next_attempt_at=now).on_conflict_do_nothing(index_elements=[Notification.event_key]))
    db.commit()
