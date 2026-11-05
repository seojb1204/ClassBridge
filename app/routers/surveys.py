"""설문 API. 익명 제출 경로는 접근 로그에서 제외된다 (core/middleware.py)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response as HttpResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import FeatureDisabled
from app.core.permissions import P
from app.db import get_db
from app.infra.excel import build_workbook
from app.repositories import surveys as repo
from app.schemas.surveys import (
    SubmitIn,
    SurveyCreateIn,
    SurveyOut,
    SurveyStaffListOut,
    SurveyStudentListOut,
    SurveyStudentOut,
    SurveyUpdateIn,
)
from app.services import feedback_management as management
from app.services import survey_service as svc
from app.services.survey_service import QuestionInput

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


def feature_on(request: Request) -> None:
    if not request.app.state.settings.feature_surveys:
        raise FeatureDisabled("설문 기능이 비활성화되어 있습니다 (운영 보안 검토 후 활성화)")


def _q(items) -> list[QuestionInput]:
    return [QuestionInput(q.qtype, q.title, q.required, q.options) for q in items]


# ── 교수자·관리자 ──
@router.get("", response_model=list[SurveyStaffListOut], dependencies=[Depends(feature_on)])
def staff_list(trash: bool = False, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    counts = repo.response_counts(db)
    return [SurveyStaffListOut(id=s.id, title=s.title, course_name=s.course_name,
                               semester=s.semester, status=s.status, opens_at=s.opens_at,
                               closes_at=s.closes_at, response_count=counts.get(s.id, 0),
                               min_results=s.min_results) for s in repo.list_all(db, trash=trash)]


@router.post("", response_model=SurveyOut, status_code=201, dependencies=[Depends(feature_on)])
def create(body: SurveyCreateIn, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    return svc.create(db, p.user, body.title, body.description, _q(body.questions),
                      body.opens_at, body.closes_at, body.min_results,
                      course_name=body.course_name, semester=body.semester)


@router.get("/{survey_id}", response_model=SurveyOut, dependencies=[Depends(feature_on)])
def get_one(survey_id: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    return svc.get(db, survey_id)


@router.patch("/{survey_id}", response_model=SurveyOut, dependencies=[Depends(feature_on)])
def update(survey_id: int, body: SurveyUpdateIn, p: Principal = Depends(require(P.SURVEY_MANAGE)),
           db: Session = Depends(get_db)):
    fs = body.model_fields_set
    return svc.update(db, p.user, survey_id, title=body.title, description=body.description,
                      questions=_q(body.questions) if body.questions is not None else None,
                      opens_at=body.opens_at, closes_at=body.closes_at, min_results=body.min_results,
                      course_name=body.course_name, semester=body.semester, fields_set=set(fs))


@router.post("/{survey_id}/publish", response_model=SurveyOut, dependencies=[Depends(feature_on)])
def publish(survey_id: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    return svc.publish(db, p.user, survey_id)


@router.post("/{survey_id}/close", response_model=SurveyOut, dependencies=[Depends(feature_on)])
def close(survey_id: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    return svc.close(db, p.user, survey_id)


@router.post("/{survey_id}/duplicate", response_model=SurveyOut, status_code=201,
             dependencies=[Depends(feature_on)])
def duplicate(survey_id: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    return svc.duplicate(db, p.user, survey_id)


@router.delete("/{survey_id}", status_code=204, dependencies=[Depends(feature_on)])
def delete(survey_id: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    management.manage_survey(db, p.user, survey_id, "trash")


@router.get("/{survey_id}/results", dependencies=[Depends(feature_on)])
def results(survey_id: int, p: Principal = Depends(require(P.SURVEY_RESULTS)),
                     db: Session = Depends(get_db)):
    return svc.results(db, survey_id)


@router.get("/{survey_id}/export.xlsx", dependencies=[Depends(feature_on)])
def export(survey_id: int, p: Principal = Depends(require(P.EXPORT)),
                     db: Session = Depends(get_db)):
    s, header, data, summary = svc.export_rows(db, survey_id)
    content = build_workbook([("요약", ["문항", "선택지", "값"], summary), ("응답", header, data)])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return HttpResponse(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="survey-{s.id}-{stamp}.xlsx"'})


# ── 학생 ──
@router.get("/student/list", response_model=list[SurveyStudentListOut], dependencies=[Depends(feature_on)])
def student_list(p: Principal = Depends(require(P.SURVEY_RESPOND)),
                     db: Session = Depends(get_db)):
    return [SurveyStudentListOut(id=s.id, title=s.title, description=s.description,
                                 course_name=s.course_name, semester=s.semester, status=s.status,
                                 closes_at=s.closes_at, is_open=opened, participated=done)
            for s, done, opened in svc.list_for_student(db, p.user)]


@router.get("/student/{survey_id}", response_model=SurveyStudentOut, dependencies=[Depends(feature_on)])
def student_get(survey_id: int, p: Principal = Depends(require(P.SURVEY_RESPOND)),
                     db: Session = Depends(get_db)):
    s, done = svc.get_for_student(db, p.user, survey_id)
    base = SurveyOut.model_validate(s).model_dump()
    return SurveyStudentOut(**base, participated=done, is_open=svc.is_open(s, datetime.now(timezone.utc)))


@router.post("/{survey_id}/responses", status_code=201, dependencies=[Depends(feature_on)])
def submit(survey_id: int, body: SubmitIn, p: Principal = Depends(require(P.SURVEY_RESPOND)),
           db: Session = Depends(get_db)):
    svc.submit(db, p.user, survey_id, body.answers)
    return {"ok": True, "message": "응답이 익명으로 제출되었습니다"}


class SurveyPurgeIn(BaseModel):
    confirmation: str
    response_count: int


@router.post("/{sid}/trash", status_code=204, dependencies=[Depends(feature_on)])
def trash_survey(sid: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    management.manage_survey(db, p.user, sid, "trash")


@router.post("/{sid}/restore", status_code=204, dependencies=[Depends(feature_on)])
def restore_survey(sid: int, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    management.manage_survey(db, p.user, sid, "restore")


@router.post("/{sid}/purge", status_code=204, dependencies=[Depends(feature_on)])
def purge_survey(sid: int, body: SurveyPurgeIn, p: Principal = Depends(require(P.SURVEY_MANAGE)),
                     db: Session = Depends(get_db)):
    management.manage_survey(db, p.user, sid, "purge", body.confirmation, body.response_count)
