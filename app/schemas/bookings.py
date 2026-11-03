from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field


class SlotOut(BaseModel):
    id: int
    start_at: datetime
    end_at: datetime
    kind: str
    capacity: int
    remaining: int
    status: str
    location: str
    note: str
    mine: bool
    bookable: bool
    reason: str


class SlotCreateIn(BaseModel):
    start_date: date
    start_time: time
    end_time: time
    duration_minutes: int = Field(ge=5, le=240)
    kind: Literal["individual", "group"] = "individual"
    capacity: int = Field(default=1, ge=1, le=100)
    break_minutes: int | None = Field(default=None, ge=0, le=120)
    repeat_weeks: int = Field(default=1, ge=1, le=26)
    weekdays: list[int] | None = None
    location: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=500)


class SlotUpdateIn(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=100)
    kind: Literal["individual", "group"] | None = None
    location: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    start_at: datetime | None = None
    end_at: datetime | None = None


class SlotCancelIn(BaseModel):
    force: bool = False
    reason: str = Field(default="", max_length=500)


class BlackoutIn(BaseModel):
    day: date
    reason: str = Field(default="", max_length=200)


class BlackoutOut(BaseModel):
    id: int
    day: date
    reason: str

    model_config = {"from_attributes": True}


class BookingCreateIn(BaseModel):
    slot_id: int
    student_id: int | None = None  # 교수자·관리자만 사용 가능 (서버에서 검증)
    topic: str = Field(default="", max_length=500)


class BookingCancelIn(BaseModel):
    reason: str = Field(default="", max_length=500)


class BookingRescheduleIn(BaseModel):
    new_slot_id: int
    reason: str = Field(default="", max_length=500)


class OutcomeIn(BaseModel):
    outcome: Literal["completed", "no_show"]


class NoteIn(BaseModel):
    note: str = Field(max_length=10000)


class SlotBrief(BaseModel):
    id: int
    start_at: datetime
    end_at: datetime
    kind: str
    location: str

    model_config = {"from_attributes": True}


class MyBookingOut(BaseModel):
    """학생 본인용: 상담 기록(professor_note)은 포함하지 않는다."""
    id: int
    status: str
    topic: str
    cancel_reason: str
    created_at: datetime
    slot: SlotBrief

    model_config = {"from_attributes": True}


class StaffBookingOut(MyBookingOut):
    student_id: int
    student_name: str
    student_email: str
    professor_note: str


class EventOut(BaseModel):
    id: int
    actor_id: int
    action: str
    detail: str
    at: datetime

    model_config = {"from_attributes": True}
