from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utcnow


class Slot(Base):
    """교수자가 연 상담 가능 시간 1칸."""

    __tablename__ = "slots"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="ck_slots_time_order"),
        CheckConstraint("capacity >= 1", name="ck_slots_capacity_pos"),
        # 정원 초과는 DB가 최종적으로 거부한다
        CheckConstraint("booked_count >= 0 AND booked_count <= capacity", name="ck_slots_booked_range"),
        CheckConstraint("kind IN ('individual','group')", name="ck_slots_kind"),
        CheckConstraint("kind = 'group' OR capacity = 1", name="ck_slots_individual_cap"),
        CheckConstraint("status IN ('open','cancelled')", name="ck_slots_status"),
        Index("ix_slots_start_at", "start_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    kind: Mapped[str] = mapped_column(String(20), default="individual")
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    booked_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="open")
    location: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    series_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('booked','cancelled','completed','no_show')", name="ck_bookings_status"
        ),
        # 학생 1명당 활성 예약 1건: DB 수준 보장 (SQLite·PostgreSQL 모두 부분 인덱스 지원)
        Index(
            "uq_bookings_one_active_per_student",
            "student_id",
            unique=True,
            sqlite_where=text("status = 'booked'"),
            postgresql_where=text("status = 'booked'"),
        ),
        Index("ix_bookings_slot_status", "slot_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="booked")
    topic: Mapped[str] = mapped_column(String(500), default="")
    # 상담 기록: 교수자·관리자만 열람. 외부 AI로 절대 전송하지 않는다.
    professor_note: Mapped[str] = mapped_column(Text, default="")
    cancel_reason: Mapped[str] = mapped_column(String(500), default="")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    slot: Mapped[Slot] = relationship(lazy="joined")


class BookingEvent(Base):
    """예약 변경 이력 (누가, 언제, 무엇을)."""

    __tablename__ = "booking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(String(500), default="")
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Blackout(Base):
    """상담 불가 날짜 (한국 날짜 기준)."""

    __tablename__ = "blackouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day: Mapped[date] = mapped_column(Date, unique=True)
    reason: Mapped[str] = mapped_column(String(200), default="")
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
