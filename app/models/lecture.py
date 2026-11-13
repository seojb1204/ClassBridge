"""Staff-only lecture occurrences, separate from bookable consultation slots."""

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime, utcnow


class Lecture(Base):
    __tablename__ = "lectures"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_lectures_time_order"),
        CheckConstraint("status IN ('active','cancelled')", name="ck_lectures_status"),
        Index("ix_lectures_start_at", "start_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(200), default="")
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(20), default="active")
    series_id: Mapped[str] = mapped_column(String(36), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
