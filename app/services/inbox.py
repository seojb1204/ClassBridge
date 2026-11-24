"""Enqueue in the caller's transaction; never wake or poll the DB independently."""
import re

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db import utcnow
from app.models import Booking, User
from app.models.booking import BookingEvent
from app.models.inbox import InboxNotification
from app.timeutil import kst_date, to_kst

LABELS = {"created": "새 상담 예약", "changed": "상담 예약 변경", "cancelled": "상담 예약 취소",
          "slot_changed": "상담 정보 변경", "suggestion": "새 건의 접수", "custom_reminder": "개인 예약 알림"}


def enqueue(db, event_key: str, kind: str, *, available_at=None):
    if kind not in LABELS or kind == "custom_reminder":
        raise ValueError("Unsupported inbox notification kind")
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    for recipient in db.scalars(select(User.id).where(User.role.in_(("professor", "admin")), User.is_active.is_(True))):
        db.execute(insert(InboxNotification).values(recipient_id=recipient, event_key=event_key,
            kind=kind, created_on=kst_date(utcnow()), available_at=available_at or utcnow()).on_conflict_do_nothing(
                index_elements=[InboxNotification.recipient_id, InboxNotification.event_key]))


BOOKING_ACTIONS = {
    "created": {"book", "book_by_staff"},
    "changed": {"rescheduled"},
    "cancelled": {"cancel", "cancel_by_staff", "cancel_by_slot"},
    "slot_changed": {"slot_changed"},
}
STATUS_LABELS = {"booked": "예약됨", "cancelled": "취소됨", "completed": "상담 완료",
                 "no_show": "미참석", "expired": "결과 확인 필요"}


def booking_targets(db, rows):
    """Resolve already-authorized inbox rows in one query, never by guessed booking IDs.

    Callers must filter recipient, availability and staff permissions first. Neither
    anonymous suggestion notices nor personal reminders are linked to bookings.
    """
    event_ids = {}
    for row in rows:
        match = re.fullmatch(r"booking-event-([1-9][0-9]*)", row.event_key)
        if row.kind in BOOKING_ACTIONS and match:
            # Bound legacy/corrupt keys before passing them to an integer DB column.
            event_id = int(match[1]) if len(match[1]) <= 19 else 0
            if 0 < event_id <= 9223372036854775807:
                event_ids[row.id] = event_id
    if not event_ids:
        return {}
    matches = {event_id: (action, booking, student) for event_id, action, booking, student in db.execute(
        select(BookingEvent.id, BookingEvent.action, Booking, User)
        .join(Booking, Booking.id == BookingEvent.booking_id)
        .outerjoin(User, User.id == Booking.student_id)
        .where(BookingEvent.id.in_(set(event_ids.values())))
    ).unique()}
    resolved = {}
    for row in rows:
        match = matches.get(event_ids.get(row.id))
        if match and match[0] in BOOKING_ACTIONS[row.kind] and match[1].slot is not None:
            resolved[row.id] = (match[1], match[2])
    return resolved


def booking_summary(booking, student):
    """Minimal in-app staff summary, never a push payload or historical snapshot."""
    return {"student_name": booking.applicant_name or (student.name if student else "예약자"),
            "start_at": to_kst(booking.slot.start_at).isoformat(timespec="seconds"),
            "end_at": to_kst(booking.slot.end_at).isoformat(timespec="seconds"),
            "status": booking.status, "status_label": STATUS_LABELS.get(booking.status, "상태 확인 필요"),
            "source": "current"}


def public_item(row, target=None):
    suggestion = row.kind == "suggestion"
    summary = booking_summary(*target) if target else None
    body = row.message if row.kind == "custom_reminder" else (
        "건의함에서 새 건의를 확인하세요." if suggestion else "연결된 예약 정보를 확인할 수 없습니다.")
    if summary:
        booking, _ = target
        start, end = to_kst(booking.slot.start_at), to_kst(booking.slot.end_at)
        weekday = "월화수목금토일"[start.weekday()]
        end_label = end.strftime("%H:%M") if start.date() == end.date() else end.strftime("%m/%d %H:%M")
        body = f"현재 예약 · {start.month}/{start.day}({weekday}) {start:%H:%M}–{end_label} · {summary['status_label']}"
    return {"id": row.id, "kind": row.kind, "title": LABELS[row.kind],
            "body": body, "booking_summary": summary,
            "url": "/#/suggestions" if suggestion else f"/#/inbox/{row.id}",
            "created_on": row.created_on.isoformat(), "arrived_on": kst_date(row.available_at).isoformat(),
            "arrived_at": to_kst(row.available_at).isoformat(timespec="seconds"),
            "read": row.read_at is not None}
