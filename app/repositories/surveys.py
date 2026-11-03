from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Answer, Participation, Question, Response, Survey


def get(db: Session, survey_id: int, lock: bool = False) -> Survey | None:
    stmt = select(Survey).where(Survey.id == survey_id)
    if lock:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def list_all(db: Session) -> list[Survey]:
    return list(db.execute(select(Survey).order_by(Survey.created_at.desc(), Survey.id.desc())).scalars())


def list_by_status(db: Session, statuses: tuple[str, ...]) -> list[Survey]:
    return list(db.execute(
        select(Survey).where(Survey.status.in_(statuses)).order_by(Survey.created_at.desc())
    ).scalars())


def response_counts(db: Session) -> dict[int, int]:
    rows = db.execute(select(Response.survey_id, func.count()).group_by(Response.survey_id)).all()
    return {sid: n for sid, n in rows}


def response_count(db: Session, survey_id: int) -> int:
    return db.execute(select(func.count()).select_from(Response).where(Response.survey_id == survey_id)).scalar_one()


def participated_survey_ids(db: Session, user_id: int) -> set[int]:
    return set(db.execute(select(Participation.survey_id).where(Participation.user_id == user_id)).scalars())


def answers_for(db: Session, survey_id: int) -> list[Answer]:
    return list(db.execute(
        select(Answer).join(Response, Response.id == Answer.response_id).where(Response.survey_id == survey_id)
    ).scalars())


def replace_questions(survey: Survey, questions: list[Question]) -> None:
    survey.questions.clear()
    survey.questions.extend(questions)
