"""Enqueue in the caller's transaction; never wake or poll the DB independently."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.db import utcnow
from app.models import User
from app.models.inbox import InboxNotification
from app.timeutil import kst_date, to_kst

LABELS = {"created": "새 상담 예약", "changed": "상담 예약 변경", "cancelled": "상담 예약 취소",
          "slot_changed": "상담 정보 변경", "suggestion": "새 건의 접수"}


def enqueue(db, event_key: str, kind: str, *, available_at=None):
    if kind not in LABELS:
        raise ValueError("Unsupported inbox notification kind")
    insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
    for recipient in db.scalars(select(User.id).where(User.role.in_(("professor", "admin")), User.is_active.is_(True))):
        db.execute(insert(InboxNotification).values(recipient_id=recipient, event_key=event_key,
            kind=kind, created_on=kst_date(utcnow()), available_at=available_at or utcnow()).on_conflict_do_nothing(
                index_elements=[InboxNotification.recipient_id, InboxNotification.event_key]))


def public_item(row):
    suggestion = row.kind == "suggestion"
    return {"id": row.id, "kind": row.kind, "title": LABELS[row.kind],
            "body": "새 건의가 접수되었습니다. 건의함에서 확인하세요." if suggestion
                else "상담 예약 관련 변경이 있습니다. 예약 관리에서 확인하세요.",
            "url": "/#/suggestions" if suggestion else "/#/bookings",
            "created_on": row.created_on.isoformat(), "arrived_on": kst_date(row.available_at).isoformat(),
            "arrived_at": to_kst(row.available_at).isoformat(timespec="seconds"),
            "read": row.read_at is not None}
