"""An account-scoped inbox, independent of browser push registration."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import Forbidden, NotFound
from app.core.permissions import P
from app.db import get_db, utcnow
from app.models.inbox import InboxNotification
from app.services.inbox import public_item

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


def staff(p: Principal = Depends(require(P.BOOKING_MANAGE))):
    if p.role not in ("professor", "admin"):
        raise Forbidden("교수자·관리자 알림함입니다")
    return p


@router.get("")
def listing(p: Principal = Depends(staff), db: Session = Depends(get_db)):
    own = (InboxNotification.recipient_id == p.id) & (InboxNotification.available_at <= utcnow())
    rows = db.scalars(select(InboxNotification).where(own).order_by(InboxNotification.id.desc()).limit(100))
    return {"items": [public_item(row) for row in rows],
            "unread": db.scalar(select(func.count()).select_from(InboxNotification)
                                .where(own, InboxNotification.read_at.is_(None)))}


@router.put("/{notification_id}/read")
def read(notification_id: int, p: Principal = Depends(staff), db: Session = Depends(get_db)):
    row = db.scalar(select(InboxNotification).where(InboxNotification.id == notification_id,
        InboxNotification.recipient_id == p.id, InboxNotification.available_at <= utcnow()).with_for_update())
    if row is None:
        raise NotFound("알림을 찾을 수 없습니다")
    if row.read_at is None:
        row.read_at = utcnow()
    db.commit()
    return {"ok": True}
