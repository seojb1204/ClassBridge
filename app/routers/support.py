"""Account-linked private support, with ownership checked on every operation."""
import re
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import Forbidden, NotFound
from app.core.permissions import P
from app.db import get_db, utcnow
from app.models import User
from app.models.support import SupportMessage, SupportTicket
from app.repositories import audit

router = APIRouter(prefix="/api/support", tags=["support"])
Status = Literal["received", "reviewing", "completed"]


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def clean(cls, value):
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value).strip()
        if not value:
            raise ValueError("내용을 입력하세요")
        return value


class TicketIn(MessageIn):
    title: str = Field(min_length=1, max_length=120)
    category: Literal["bug", "feature", "help"]
    # Only an internal route, never full URLs, queries, cookies or diagnostics.
    page_path: str = Field(default="", max_length=200, pattern=r"^(?:/[A-Za-z0-9_/-]*)?$")

    @field_validator("title")
    @classmethod
    def title_clean(cls, value):
        return cls.clean(value)


class ReadIn(BaseModel):
    updated_at: datetime


class StatusIn(BaseModel):
    status: Status


def _scope(p, inbox):
    if inbox and not p.can(P.SUPPORT_MANAGE):
        raise Forbidden("개발자 문의 관리 권한이 없습니다")


def _ticket(db, p, tid, inbox, lock=False):
    _scope(p, inbox)
    stmt = select(SupportTicket).where(SupportTicket.id == tid)
    if not inbox:
        stmt = stmt.where(SupportTicket.owner_id == p.user.id)
    if lock:
        stmt = stmt.with_for_update()
    item = db.scalar(stmt)
    if item is None:
        raise NotFound("문의를 찾을 수 없습니다")
    return item


def _summary(item, inbox=False):
    return dict(id=item.id, title=item.title, category=item.category, status=item.status,
                created_at=item.created_at, updated_at=item.updated_at,
                unread=item.developer_unread if inbox else item.owner_unread)


@router.get("/counts")
def counts(p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    mine = db.scalar(select(func.count()).select_from(SupportTicket).where(
        SupportTicket.owner_id == p.user.id, SupportTicket.owner_unread.is_(True)))
    inbox = db.scalar(select(func.count()).select_from(SupportTicket).where(
        SupportTicket.developer_unread.is_(True))) if p.can(P.SUPPORT_MANAGE) else 0
    return {"mine": mine, "inbox": inbox}


@router.get("/tickets")
def tickets(inbox: bool = False, offset: int = Query(0, ge=0),
            p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    _scope(p, inbox)
    stmt = select(SupportTicket)
    if not inbox:
        stmt = stmt.where(SupportTicket.owner_id == p.user.id)
    items = db.scalars(stmt.order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc()).offset(offset).limit(50))
    return [_summary(item, inbox) for item in items]


@router.post("/tickets", status_code=201)
def create(body: TicketIn, request: Request, p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    request.app.state.support_limiter.hit(str(p.user.id))
    item = SupportTicket(owner_id=p.user.id, title=body.title, category=body.category, page_path=body.page_path)
    db.add(item)
    db.flush()
    db.add(SupportMessage(ticket_id=item.id, is_developer=False, content=body.content))
    db.commit()
    return {"id": item.id}


@router.get("/tickets/{tid}")
def detail(tid: int, inbox: bool = False, p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    item = _ticket(db, p, tid, inbox)
    messages = db.scalars(select(SupportMessage).where(SupportMessage.ticket_id == tid).order_by(SupportMessage.id))
    result = {**_summary(item, inbox), "page_path": item.page_path,
              "messages": [dict(id=m.id, is_developer=m.is_developer, content=m.content, created_at=m.created_at)
                           for m in messages]}
    if inbox:
        owner = db.get(User, item.owner_id)
        result["owner"] = {"name": owner.name, "email": owner.email}
    return result


@router.post("/tickets/{tid}/read", status_code=204)
def mark_read(tid: int, body: ReadIn, inbox: bool = False,
              p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    item = _ticket(db, p, tid, inbox, lock=True)
    # A reply/status arriving since the displayed version must stay unread.
    if item.updated_at == body.updated_at:
        if inbox:
            item.developer_unread = False
        else:
            item.owner_unread = False
    db.commit()


@router.post("/tickets/{tid}/messages", status_code=201)
def respond(tid: int, body: MessageIn, request: Request, inbox: bool = False,
            p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    item = _ticket(db, p, tid, inbox, lock=True)
    request.app.state.support_limiter.hit(str(p.user.id))
    db.add(SupportMessage(ticket_id=tid, is_developer=inbox, content=body.content))
    item.updated_at = utcnow()
    if inbox:
        item.owner_unread = True
        if item.status == "received":
            item.status = "reviewing"
        audit.add(db, p.user.id, "support.reply", "support", tid)
    else:
        item.developer_unread = True
        if item.status == "completed":
            item.status = "received"
    db.commit()
    return {"ok": True}


@router.put("/tickets/{tid}/status", status_code=204)
def status(tid: int, body: StatusIn, p: Principal = Depends(require(P.SUPPORT_MANAGE)), db: Session = Depends(get_db)):
    item = _ticket(db, p, tid, True, lock=True)
    if item.status != body.status:
        item.status = body.status
        item.updated_at = utcnow()
        item.owner_unread = True
        audit.add(db, p.user.id, "support.status", "support", tid, {"status": body.status})
    db.commit()
