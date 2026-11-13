"""Staff calendar only. Does not change consultation availability or send notifications."""

from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import NotFound
from app.core.permissions import P
from app.db import get_db
from app.models.lecture import Lecture
from app.repositories import audit
from app.services.lecture_policy import ensure_lecture_allowed, lock_calendar

router = APIRouter(prefix="/api/lectures", tags=["lectures"])
KST = ZoneInfo("Asia/Seoul")


class LectureInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=200)
    date: date
    start_time: time
    end_time: time
    weeks: int = Field(default=1, ge=1, le=26)

    @field_validator("title", "location")
    @classmethod
    def trim(cls, value, info):
        value = value.strip()
        if info.field_name == "title" and not value:
            raise ValueError("강의명을 입력하세요")
        return value

    @model_validator(mode="after")
    def valid_times(self):
        if self.start_time.tzinfo or self.end_time.tzinfo or self.end_time <= self.start_time:
            raise ValueError("한국 시간으로 같은 날의 시작·종료 시간을 입력하세요")
        if self.start_time.second or self.end_time.second or self.start_time.microsecond or self.end_time.microsecond:
            raise ValueError("분 단위로 입력하세요")
        if not 2000 <= self.date.year <= 2100:
            raise ValueError("날짜를 확인하세요")
        return self


def output(row):
    return {
        **{k: getattr(row, k) for k in ("id", "title", "location", "start_at", "end_at", "status", "series_id")},
        "event_type": "lecture",
        "bookable": False,
    }


@router.get("")
def listing(
    start: date,
    days: int = Query(7, ge=1, le=90),
    p: Principal = Depends(require(P.SLOT_MANAGE)),
    db: Session = Depends(get_db),
):
    a = datetime.combine(start, time(), KST)
    rows = db.scalars(
        select(Lecture)
        .where(Lecture.start_at < a + timedelta(days=days), Lecture.end_at > a, Lecture.status == "active")
        .order_by(Lecture.start_at, Lecture.id)
    )
    return [output(r) for r in rows]


@router.post("", status_code=201)
def create(body: LectureInput, p: Principal = Depends(require(P.SLOT_MANAGE)), db: Session = Depends(get_db)):
    lock_calendar(db)
    series = str(uuid4())
    rows = []
    for week in range(body.weeks):
        day = body.date + timedelta(weeks=week)
        ensure_lecture_allowed(db, datetime.combine(day, body.start_time, KST), datetime.combine(day, body.end_time, KST))
        row = Lecture(
            title=body.title,
            location=body.location,
            start_at=datetime.combine(day, body.start_time, KST),
            end_at=datetime.combine(day, body.end_time, KST),
            series_id=series,
            created_by_id=p.id,
        )
        db.add(row)
        rows.append(row)
    audit.add(db, p.id, "lecture.create", "lecture_series", series, {"count": len(rows)})
    db.commit()
    return [output(row) for row in rows]


@router.patch("/{identifier}")
def update(
    identifier: int, body: LectureInput, p: Principal = Depends(require(P.SLOT_MANAGE)), db: Session = Depends(get_db)
):
    lock_calendar(db)
    row = db.get(Lecture, identifier)
    if not row or row.status != "active":
        raise NotFound("강의를 찾을 수 없습니다")
    if body.weeks != 1:
        from app.core.errors import BadRequest

        raise BadRequest("이번 강의만 수정할 수 있습니다")
    ensure_lecture_allowed(
        db, datetime.combine(body.date, body.start_time, KST), datetime.combine(body.date, body.end_time, KST), identifier
    )
    row.title, row.location = body.title, body.location
    row.start_at = datetime.combine(body.date, body.start_time, KST)
    row.end_at = datetime.combine(body.date, body.end_time, KST)
    audit.add(db, p.id, "lecture.update", "lecture", identifier)
    db.commit()
    return output(row)


@router.post("/{identifier}/cancel")
def cancel(
    identifier: int, series: bool = False, p: Principal = Depends(require(P.SLOT_MANAGE)), db: Session = Depends(get_db)
):
    lock_calendar(db)
    row = db.get(Lecture, identifier)
    if not row:
        raise NotFound("강의를 찾을 수 없습니다")
    rows = list(db.scalars(select(Lecture).where(Lecture.series_id == row.series_id))) if series else [row]
    for item in rows:
        item.status = "cancelled"
    audit.add(db, p.id, "lecture.cancel", "lecture", identifier, {"series": series, "count": len(rows)})
    db.commit()
    return {"cancelled": len(rows)}
