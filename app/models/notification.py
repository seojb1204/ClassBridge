"""Durable, minimal booking mail outbox. No credentials or consultation text."""
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class Notification(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        CheckConstraint("status IN ('pending','sending','sent','uncertain','failed','reauth','skipped')",
                        name="ck_notification_status"),
        Index("ix_notification_due", "status", "next_attempt_at"),
        Index("ix_notification_chain", "chain_id", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_key: Mapped[str] = mapped_column(String(100), unique=True)
    chain_id: Mapped[int] = mapped_column(Integer)
    booking_id: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    sender: Mapped[str] = mapped_column(String(254))
    recipient: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    error_code: Mapped[str] = mapped_column(String(50), default="")
    gmail_id: Mapped[str] = mapped_column(String(100), default="")
    channel: Mapped[str] = mapped_column(String(10), default="gmail")
    subscription_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {"sqlite_autoincrement": True}
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("auth_sessions.id", ondelete="CASCADE"), index=True)
    endpoint_hash: Mapped[str] = mapped_column(String(64), unique=True)
    subscription: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
