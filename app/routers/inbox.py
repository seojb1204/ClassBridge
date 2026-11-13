"""An account-scoped inbox, independent of browser push registration."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
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
def listing(p: Principal = Depends(staff), db: Session = Depends(get_db),
            limit: int = Query(100, ge=1, le=100), before_id: int | None = Query(None, ge=1),
            unread_only: bool = False):
    # "Newest" means most recently available, not insertion/receipt order.
    own = (InboxNotification.recipient_id == p.id) & (InboxNotification.available_at <= utcnow())
    stmt = select(InboxNotification).where(own)
    if unread_only:
        stmt = stmt.where(InboxNotification.read_at.is_(None))
    if before_id is not None:
        cursor = db.scalar(select(InboxNotification).where(own, InboxNotification.id == before_id))
        if cursor is None:
            raise NotFound("알림 페이지를 찾을 수 없습니다. 새로고침해 주세요")
        stmt = stmt.where(or_(InboxNotification.available_at < cursor.available_at,
            and_(InboxNotification.available_at == cursor.available_at, InboxNotification.id < cursor.id)))
    rows = list(db.scalars(stmt.order_by(InboxNotification.available_at.desc(),
                                        InboxNotification.id.desc()).limit(limit + 1)))
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {"items": [public_item(row) for row in rows],
            "unread": db.scalar(select(func.count()).select_from(InboxNotification)
                                .where(own, InboxNotification.read_at.is_(None))),
            "has_more": has_more, "next_before_id": rows[-1].id if has_more else None}


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
