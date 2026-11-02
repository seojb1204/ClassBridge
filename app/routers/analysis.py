from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.permissions import P
from app.db import get_db
from app.services import analysis_service

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


class AnalyzeIn(BaseModel):
    source: Literal["suggestions", "survey"]
    survey_id: int | None = None


@router.post("")
def analyze(body: AnalyzeIn, request: Request, p: Principal = Depends(require(P.AI_ANALYZE)),
            db: Session = Depends(get_db)):
    st = request.app.state
    if st.settings.ai_mode == "external":
        st.ai_limiter.hit(f"ai:{p.id}")
    return analysis_service.analyze(db, st.settings.ai_mode, st.ai_client, body.source, body.survey_id)
