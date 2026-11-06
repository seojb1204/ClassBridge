"""예약 화면 대표 공지. 기존 JSON 설정을 사용하며 일반 운영 설정 권한과 분리한다."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import Conflict
from app.core.permissions import P
from app.db import get_db, utcnow
from app.models import AppSetting
from app.repositories import audit

router = APIRouter(prefix="/api/announcement", tags=["announcement"])
KEY = "booking_announcement"


class AnnouncementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(max_length=100)
    body: str = Field(max_length=2000)
    published: bool
    revision: int = Field(ge=0, strict=True)

    @field_validator("title", "body")
    @classmethod
    def trim(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def published_content(self):
        if self.published and (not self.title or not self.body):
            raise ValueError("게시하려면 제목과 내용을 입력하세요")
        return self


@router.get("")
def get_announcement(p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    row = db.get(AppSetting, KEY)
    value = row.value if row else {"title": "", "body": "", "published": False, "revision": 0, "updated_at": None}
    if p.can(P.ANNOUNCEMENT_MANAGE):
        return {"announcement": value}
    return {"announcement": {k: value[k] for k in ("title", "body", "updated_at")}
            if value["published"] else None}


@router.put("")
def put_announcement(body: AnnouncementIn, p: Principal = Depends(require(P.ANNOUNCEMENT_MANAGE)),
                     db: Session = Depends(get_db)):
    value = {"title": body.title, "body": body.body, "published": body.published,
             "revision": body.revision + 1, "updated_at": utcnow().isoformat()}
    try:
        if body.revision == 0:
            db.add(AppSetting(key=KEY, value=value))
            db.flush()
        else:
            changed = db.execute(update(AppSetting).where(
                AppSetting.key == KEY, AppSetting.value["revision"].as_integer() == body.revision,
            ).values(value=value), execution_options={"synchronize_session": False})
            if changed.rowcount != 1:
                raise Conflict("다른 사용자가 공지를 변경했습니다. 창을 닫고 새로고침한 뒤 다시 수정하세요")
        audit.add(db, p.id, "announcement.update", "announcement", KEY,
                  {"revision": value["revision"], "published": body.published})
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("공지가 이미 변경되었습니다. 창을 닫고 새로고침한 뒤 다시 수정하세요") from exc
    except Exception:
        db.rollback()
        raise
    return {"announcement": value}
