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
from app.services.personal_alerts import EMAIL_PAUSED, Preferences, devices, email_paused, preferences

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/notification-summary")
def notification_summary(request: Request, p: Principal = Depends(require(P.BOOKING_MANAGE)),
                         db: Session = Depends(get_db)):
    from app.models import PushSubscription
    settings = request.app.state.settings
    channels = {}
    for channel, enabled, recipient in (
        ("gmail", settings.gmail_notifications_enabled, settings.gmail_professor_email),
        ("push", settings.push_enabled, settings.push_professor_email),
    ):
        own = recipient == p.user.email if channel == 'gmail' else True
        if channel == 'gmail' and email_paused(db):
            enabled = False
        scope = (Notification.channel == channel, Notification.recipient == p.user.email)
        counts = dict(db.execute(select(Notification.status, func.count())
                                .where(*scope).group_by(Notification.status)).all())
        channels[channel] = {"enabled": enabled, "paused": channel == "gmail" and email_paused(db), "recipient": own,
                             "attention": sum(counts.get(s, 0) for s in ("failed", "reauth", "uncertain")),
                             "pending": sum(counts.get(s, 0) for s in ("pending", "sending")),
                             "last_success": db.scalar(select(func.max(Notification.sent_at)).where(*scope))}
    channels["push"]["session_registered"] = bool(db.scalar(select(PushSubscription.id)
        .where(PushSubscription.session_id == p.session.id).limit(1)))
    return channels


@router.get("/push-config")
def push_config(request: Request, p: Principal = Depends(require(P.BOOKING_MANAGE))):
    s = request.app.state.settings
    return {"enabled": s.push_enabled, "session": p.session.id,
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
    if not s.push_enabled:
        raise Forbidden("휴대폰 알림 발송이 비활성화되어 있습니다")
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


@router.get("/personal-alerts")
def read_preferences(p: Principal = Depends(require(P.BOOKING_MANAGE))):
    return preferences(p.user)


@router.put("/personal-alerts")
def save_preferences(body: Preferences, p: Principal = Depends(require(P.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    p.user.alert_preferences = body.model_dump()
    db.commit()
    return body


class DeviceIn(BaseModel):
    endpoint: str


def current_device(db, session_id, endpoint):
    import hashlib

    from app.models import PushSubscription
    digest = hashlib.sha256(endpoint.encode()).hexdigest()
    return db.scalar(select(PushSubscription).where(PushSubscription.session_id == session_id,
                                                   PushSubscription.endpoint_hash == digest))


@router.post("/push-device-state")
def device_state(body: DeviceIn, p: Principal = Depends(require(P.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    return {"registered": current_device(db, p.session.id, body.endpoint) is not None}


@router.post("/push-device-remove")
def remove_device(body: DeviceIn, p: Principal = Depends(require(P.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    device = current_device(db, p.session.id, body.endpoint)
    if device:
        db.delete(device)
        db.commit()
    return {"ok": True}


@router.post("/push-test")
def test_device(request: Request, body: DeviceIn, p: Principal = Depends(require(P.BOOKING_MANAGE)),
                db: Session = Depends(get_db)):
    from types import SimpleNamespace

    from app.infra.gmail import MailFailure
    from app.infra.push import PushSender

    if not request.app.state.settings.push_enabled:
        raise Conflict("휴대폰 알림이 비활성화되어 있습니다")
    # Match the browser's endpoint rather than sending to every device on a shared session.
    device = current_device(db, p.session.id, body.endpoint)
    if not device:
        raise Conflict("먼저 이 기기를 등록해 주세요")
    row = SimpleNamespace(subscription_id=device.id, recipient=p.user.email, payload={"kind": "test"},
                          event_key="device-test")
    db.rollback()
    try:
        PushSender(request.app.state.settings, request.app.state.SessionLocal).send(row)
    except MailFailure as exc:
        raise Conflict("테스트 발송에 실패했습니다. 기기 등록과 발송 설정을 확인해 주세요") from exc
    return {"accepted": True}


class EmailDelivery(BaseModel):
    paused: bool


@router.put("/email-delivery")
def email_delivery(body: EmailDelivery, p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    from sqlalchemy import update

    from app.repositories.settings import put
    put(db, EMAIL_PAUSED, body.paused)
    if body.paused:
        db.execute(update(Notification).where(Notification.channel == "gmail", Notification.status == "pending")
                   .values(status="skipped", error_code="email_paused"))
    audit_repo.add(db, p.id, "email.pause" if body.paused else "email.resume", "settings", EMAIL_PAUSED)
    db.commit()
    return body


@router.get("/notifications")
def notifications(request: Request, p: Principal = Depends(require(P.SETTINGS_MANAGE)),
                  db: Session = Depends(get_db)):
    counts = dict(db.execute(select(Notification.status, func.count()).group_by(Notification.status)).all())
    rows = db.scalars(select(Notification).where(Notification.status.not_in(("sent", "skipped")))
                      .order_by(Notification.id).limit(50)).all()
    settings = request.app.state.settings
    device_count = db.scalar(select(func.count()).select_from(devices(utcnow()).subquery()))
    paused = email_paused(db)
    return {"enabled": settings.gmail_notifications_enabled, "push_enabled": settings.push_enabled,
            "push_devices": device_count, "email_paused": paused,
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


