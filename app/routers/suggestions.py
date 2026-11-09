from __future__ import annotations

import hashlib
import hmac
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import SESSION_COOKIE, Principal, require
from app.core.errors import FeatureDisabled, Forbidden
from app.core.permissions import P
from app.db import get_db, utcnow
from app.models.suggestion import SuggestionReply
from app.repositories import suggestions as repo
from app.services import feedback_management as management
from app.services import suggestion_service as svc

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])
Category = Literal["lecture", "assignment", "exam", "facility", "other"]


def feature_on(request: Request) -> None:
    if not request.app.state.settings.feature_suggestions:
        raise FeatureDisabled("건의함 기능이 비활성화되어 있습니다 (운영 보안 검토 후 활성화)")


class SuggestionIn(BaseModel):
    category: Category
    content: str = Field(max_length=4000)
    is_public: bool = False


class ReplyOut(BaseModel):
    id: str
    content: str
    created_on: date

    model_config = {"from_attributes": True}


class SuggestionOut(BaseModel):
    id: str
    category: str
    content: str
    submitted_on: date
    status: str
    is_public: bool
    deleted_on: date | None
    replies: list[ReplyOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class StatusIn(BaseModel):
    status: Literal["new", "reviewed", "archived"]


@router.post("", status_code=201, dependencies=[Depends(feature_on)])
def submit(body: SuggestionIn, request: Request, p: Principal = Depends(require(P.SUGGESTION_SUBMIT)),
           db: Session = Depends(get_db)):
    st = request.app.state
    svc.submit(db, st.suggestion_limiter, st.settings.secret_key, p.user, body.category, body.content,
               is_public=body.is_public)
    return {"ok": True, "message": "건의가 익명으로 접수되었습니다"}


@router.post("/anonymous", status_code=201, dependencies=[Depends(feature_on)])
def submit_anonymous(body: SuggestionIn, request: Request, db: Session = Depends(get_db)):
    if SESSION_COOKIE in request.cookies or request.headers.get("X-Anonymous-Submit") != "1":
        raise Forbidden("익명 건의 화면을 다시 열어 주세요")
    state = request.app.state
    address = request.client.host if request.client else "unknown"
    key = hmac.new(state.settings.secret_key.encode(), address.encode(), hashlib.sha256).hexdigest()
    state.guest_suggestion_limiter.hit(key)
    svc.save(db, body.category, svc.clean_content(body.content), body.is_public, utcnow())
    return {"ok": True, "message": "건의가 익명으로 접수되었습니다"}


@router.get("", response_model=list[SuggestionOut], dependencies=[Depends(feature_on)])
def search(status: str | None = None, category: str | None = None, limit: int = 100, offset: int = 0,
           trash: bool = False,
           p: Principal = Depends(require(P.SUGGESTION_READ)),
                     db: Session = Depends(get_db)):
    return with_replies(db, repo.search(db, status, category, min(max(limit, 1), 100), max(offset, 0), trash=trash))


@router.get("/stats", dependencies=[Depends(feature_on)])
def stats(p: Principal = Depends(require(P.SUGGESTION_READ)),
                     db: Session = Depends(get_db)):
    return svc.stats(db)


@router.put("/{suggestion_id}/status", response_model=SuggestionOut, dependencies=[Depends(feature_on)])
def set_status(suggestion_id: str, body: StatusIn, p: Principal = Depends(require(P.SUGGESTION_READ)),
               db: Session = Depends(get_db)):
    return svc.set_status(db, suggestion_id, body.status)


def with_replies(db, items):
    grouped = {}
    if items:
        rows = db.execute(select(SuggestionReply).where(SuggestionReply.suggestion_id.in_([s.id for s in items]))
                          .order_by(SuggestionReply.created_on, SuggestionReply.id)).scalars()
        for row in rows:
            grouped.setdefault(row.suggestion_id, []).append(ReplyOut.model_validate(row))
    return [SuggestionOut.model_validate(s).model_copy(update={"replies": grouped.get(s.id, [])}) for s in items]


@router.get("/public", response_model=list[SuggestionOut], dependencies=[Depends(feature_on)])
def public_board(limit: int = 50, offset: int = 0,
                 p: Principal = Depends(require(P.SLOT_VIEW)),
                     db: Session = Depends(get_db)):
    return with_replies(db, repo.search(db, None, None, min(max(limit, 1), 100), max(offset, 0), public_only=True))


class ReplyIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class PurgeIn(BaseModel):
    confirmation: str


@router.post("/{sid}/replies", response_model=ReplyOut, status_code=201, dependencies=[Depends(feature_on)])
def add_reply(sid: str, body: ReplyIn, p: Principal = Depends(require(P.SUGGESTION_READ)),
                     db: Session = Depends(get_db)):
    return management.reply(db, p.user, sid, body.content)


@router.post("/{sid}/trash", status_code=204, dependencies=[Depends(feature_on)])
def trash_suggestion(sid: str, p: Principal = Depends(require(P.SUGGESTION_READ)),
                     db: Session = Depends(get_db)):
    management.manage_suggestion(db, p.user, sid, "trash")


@router.post("/{sid}/restore", status_code=204, dependencies=[Depends(feature_on)])
def restore_suggestion(sid: str, p: Principal = Depends(require(P.SUGGESTION_READ)),
                     db: Session = Depends(get_db)):
    management.manage_suggestion(db, p.user, sid, "restore")


@router.post("/{sid}/purge", status_code=204, dependencies=[Depends(feature_on)])
def purge_suggestion(sid: str, body: PurgeIn, p: Principal = Depends(require(P.SUGGESTION_READ)),
                     db: Session = Depends(get_db)):
    management.manage_suggestion(db, p.user, sid, "purge", body.confirmation)
