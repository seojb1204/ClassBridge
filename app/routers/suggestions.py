from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import FeatureDisabled
from app.core.permissions import P
from app.db import get_db
from app.services import suggestion_service as svc

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])
Category = Literal["lecture", "assignment", "exam", "facility", "other"]


def feature_on(request: Request) -> None:
    if not request.app.state.settings.feature_suggestions:
        raise FeatureDisabled("건의함 기능이 비활성화되어 있습니다 (운영 보안 검토 후 활성화)")


class SuggestionIn(BaseModel):
    category: Category
    content: str = Field(max_length=4000)


class SuggestionOut(BaseModel):
    id: str
    category: str
    content: str
    submitted_on: date
    status: str

    model_config = {"from_attributes": True}


class StatusIn(BaseModel):
    status: Literal["new", "reviewed", "archived"]


@router.post("", status_code=201, dependencies=[Depends(feature_on)])
def submit(body: SuggestionIn, request: Request, p: Principal = Depends(require(P.SUGGESTION_SUBMIT)),
           db: Session = Depends(get_db)):
    st = request.app.state
    svc.submit(db, st.suggestion_limiter, st.settings.secret_key, p.user, body.category, body.content)
    return {"ok": True, "message": "건의가 익명으로 접수되었습니다"}


@router.get("", response_model=list[SuggestionOut], dependencies=[Depends(feature_on)])
def search(status: str | None = None, category: str | None = None, limit: int = 100, offset: int = 0,
           p: Principal = Depends(require(P.SUGGESTION_READ)), db: Session = Depends(get_db)):
    return svc.search(db, status, category, limit, offset)


@router.get("/stats", dependencies=[Depends(feature_on)])
def stats(p: Principal = Depends(require(P.SUGGESTION_READ)), db: Session = Depends(get_db)):
    return svc.stats(db)


@router.put("/{suggestion_id}/status", response_model=SuggestionOut, dependencies=[Depends(feature_on)])
def set_status(suggestion_id: str, body: StatusIn, p: Principal = Depends(require(P.SUGGESTION_READ)),
               db: Session = Depends(get_db)):
    return svc.set_status(db, suggestion_id, body.status)
