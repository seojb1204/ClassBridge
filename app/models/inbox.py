"""Private, durable staff notification inbox; no student identity or content."""
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class InboxNotification(Base):
    __tablename__ = "inbox_notifications"
    __table_args__ = (
        UniqueConstraint("recipient_id", "event_key", name="uq_inbox_recipient_event"),
        Index("ix_inbox_recipient_id", "recipient_id", "id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event_key: Mapped[str] = mapped_column(String(100))
    message: Mapped[str | None] = mapped_column(String(240), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    created_on: Mapped[date] = mapped_column(Date)
    available_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
