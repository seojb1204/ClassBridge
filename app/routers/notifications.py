"""관리자 전용: 사용자·역할, 운영 설정, 감사 기록."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.permissions import P
from app.db import get_db, utcnow
from app.models import Notification
from app.repositories import audit as audit_repo

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/push-config")
def push_config(request: Request, p: Principal = Depends(require(P.BOOKING_MANAGE))):
    s = request.app.state.settings
    return {"enabled": s.push_enabled and p.user.email == s.push_professor_email,
            "public_key": s.push_public_key if s.push_enabled else ""}


@router.post("/push-subscription")
def subscribe(request: Request, body: dict = Body(...),
              p: Principal = Depends(require(P.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    import hashlib

    from sqlalchemy.exc import IntegrityError

    from app.core.errors import Forbidden
    from app.infra.push import validate_subscription
    from app.models import AuthSession, PushSubscription
    s = request.app.state.settings
    if not s.push_enabled or p.user.email != s.push_professor_email:
        raise Forbidden("지정된 교수자만 휴대폰 알림을 설정할 수 있습니다")
    subscription = validate_subscription(body)
    digest = hashlib.sha256(subscription["endpoint"].encode()).hexdigest()
    # Serialise device registration per user; never return the endpoint or encryption keys.
    from app.models import User
    db.scalar(select(User).where(User.id == p.id).with_for_update())
    row = db.scalar(select(PushSubscription).where(PushSubscription.endpoint_hash == digest).with_for_update())
    if row:
        session = db.get(AuthSession, row.session_id)
        if session and session.user_id != p.id:
            raise Conflict("기존 기기의 알림을 해제한 뒤 다시 설정하세요")
        row.session_id, row.subscription = p.session.id, subscription
    else:
        count = db.scalar(select(func.count()).select_from(PushSubscription).join(AuthSession)
                          .where(AuthSession.user_id == p.id))
        if count >= 10:
            raise Conflict("등록 기기는 최대 10개입니다. 다른 기기의 알림을 해제하세요")
        db.add(PushSubscription(session_id=p.session.id, endpoint_hash=digest, subscription=subscription))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise Conflict("기기 등록이 변경되었습니다. 다시 시도하세요") from None
    return {"ok": True}


@router.delete("/push-subscription")
def unsubscribe(p: Principal = Depends(require(P.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    from sqlalchemy import delete

    from app.models import PushSubscription
    db.execute(delete(PushSubscription).where(PushSubscription.session_id == p.session.id))
    db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(request: Request, p: Principal = Depends(require(P.SETTINGS_MANAGE)),
                  db: Session = Depends(get_db)):
    from app.models import AuthSession, PushSubscription, User
    counts = dict(db.execute(select(Notification.status, func.count()).group_by(Notification.status)).all())
    rows = db.scalars(select(Notification).where(Notification.status.not_in(("sent", "skipped")))
                      .order_by(Notification.id).limit(50)).all()
    settings = request.app.state.settings
    devices = db.scalar(select(func.count()).select_from(PushSubscription).join(AuthSession).join(User).where(
        AuthSession.expires_at > utcnow(), User.is_active.is_(True), User.role.in_(("professor", "admin")),
        User.email == settings.push_professor_email))
    return {"enabled": settings.gmail_notifications_enabled, "push_enabled": settings.push_enabled,
            "push_devices": devices,
            "sender": settings.gmail_sender_email, "recipient": settings.gmail_professor_email,
            "counts": counts,
            "last_success": db.scalar(select(func.max(Notification.sent_at))),
            "items": [{"id": r.id, "booking_id": r.booking_id, "status": r.status,
                       "channel": r.channel, "attempts": r.attempts, "error_code": r.error_code, "created_at": r.created_at,
                       "event_key": r.event_key} for r in rows]}


class NotificationResolveIn(BaseModel):
    action: Literal["retry", "confirmed_sent", "skip"]
    acknowledge: bool = False


@router.post("/notifications/{notification_id}/resolve")
def resolve_notification(notification_id: int, body: NotificationResolveIn, request: Request,
                         p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    if not body.acknowledge:
        raise BadRequest("발신함 확인 및 중복 발송 가능성을 확인해 주세요")
    row = db.scalar(select(Notification).where(Notification.id == notification_id).with_for_update())
    if row is None:
        raise NotFound("알림을 찾을 수 없습니다")
    if row.status not in ("uncertain", "reauth", "failed"):
        raise Conflict("확인이 필요한 알림만 처리할 수 있습니다")
    settings = request.app.state.settings
    if body.action == "retry":
        if not (settings.gmail_notifications_enabled if row.channel == "gmail" else settings.push_enabled):
            raise Conflict("발송 설정을 활성화한 뒤 다시 시도하세요")
        if (row.channel == "gmail"
                and (row.sender, row.recipient) != (settings.gmail_sender_email, settings.gmail_professor_email)):
            raise Conflict("기존 알림의 발신·수신자와 현재 설정이 다릅니다")
        row.status, row.attempts, row.next_attempt_at = "pending", 0, utcnow()
    elif body.action == "confirmed_sent":
        row.status, row.sent_at = "sent", utcnow()
    else:
        row.status = "skipped"
    row.error_code, row.lease_until = "", None
    audit_repo.add(db, p.id, "notification." + body.action, "notification", row.id)
    db.commit()
    return {"status": row.status}


