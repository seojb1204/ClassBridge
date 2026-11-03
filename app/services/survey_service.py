"""설문 상태 관리·익명 제출·통계.

게시 후 문항 수정 정책: 문항은 초안(draft)에서만 수정 가능.
게시 후에는 제목·설명·마감일만 변경할 수 있고, 문항을 바꾸려면 '복제'로 새 버전을 만든다.
→ 이미 제출된 응답의 의미가 바뀌지 않는다.
"""
from __future__ import annotations

import random
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, NotFound
from app.db import utcnow
from app.models import Answer, Participation, Question, Response, Survey, User
from app.models.survey import CHOICE_TYPES, QUESTION_TYPES
from app.repositories import audit as audit_repo
from app.repositories import surveys as repo
from app.services.settings_service import get_settings

MAX_QUESTIONS = 50
TEXT_LIMITS = {"short": 500, "long": 5000}


@dataclass
class QuestionInput:
    qtype: str
    title: str
    required: bool = False
    options: list[str] | None = None


def validate_questions(items: list[QuestionInput]) -> list[QuestionInput]:
    if len(items) > MAX_QUESTIONS:
        raise BadRequest(f"문항은 최대 {MAX_QUESTIONS}개입니다")
    out = []
    for i, q in enumerate(items, 1):
        if q.qtype not in QUESTION_TYPES:
            raise BadRequest(f"{i}번 문항 유형이 올바르지 않습니다")
        title = (q.title or "").strip()
        if not title or len(title) > 500:
            raise BadRequest(f"{i}번 문항 제목은 1~500자여야 합니다")
        opts = [o.strip() for o in (q.options or []) if o and o.strip()]
        if q.qtype in CHOICE_TYPES:
            if not (2 <= len(opts) <= 20):
                raise BadRequest(f"{i}번 문항 선택지는 2~20개여야 합니다")
            if len(set(opts)) != len(opts):
                raise BadRequest(f"{i}번 문항에 중복 선택지가 있습니다")
            if any(len(o) > 200 for o in opts):
                raise BadRequest(f"{i}번 문항 선택지는 200자 이하여야 합니다")
        else:
            opts = []
        out.append(QuestionInput(q.qtype, title, bool(q.required), opts))
    return out


def is_open(s: Survey, now: datetime) -> bool:
    return (s.status == "published" and (s.opens_at is None or s.opens_at <= now)
            and (s.closes_at is None or s.closes_at > now))


def _get(db: Session, survey_id: int, lock: bool = False) -> Survey:
    s = repo.get(db, survey_id, lock=lock)
    if s is None:
        raise NotFound("설문을 찾을 수 없습니다")
    return s


def _build_questions(items: list[QuestionInput]) -> list[Question]:
    return [Question(position=i, qtype=q.qtype, title=q.title, required=q.required, options=q.options or [])
            for i, q in enumerate(items)]


def create(db: Session, actor: User, title: str, description: str, questions: list[QuestionInput],
           opens_at: datetime | None, closes_at: datetime | None, min_results: int | None,
           course_name: str = "", semester: str = "") -> Survey:
    title = title.strip()
    if not title:
        raise BadRequest("제목이 필요합니다")
    _check_window(opens_at, closes_at)
    s = Survey(title=title[:200], description=description[:5000], opens_at=opens_at, closes_at=closes_at,
               min_results=min_results or get_settings(db)["survey_min_results"], created_by_id=actor.id,
               course_name=course_name.strip()[:120], semester=semester.strip()[:40])
    s.questions = _build_questions(validate_questions(questions))
    db.add(s)
    db.flush()
    audit_repo.add(db, actor.id, "survey.create", "survey", s.id, {"title": s.title})
    db.commit()
    return s


def _check_window(opens_at, closes_at):
    if opens_at and closes_at and closes_at <= opens_at:
        raise BadRequest("종료일은 시작일보다 늦어야 합니다")


def update(db: Session, actor: User, survey_id: int, *, title: str | None = None,
           description: str | None = None, questions: list[QuestionInput] | None = None,
           opens_at: datetime | None = None, closes_at: datetime | None = None,
           min_results: int | None = None, course_name: str | None = None,
           semester: str | None = None, fields_set: set[str] | None = None) -> Survey:
    fields_set = fields_set or set()
    s = _get(db, survey_id, lock=True)
    if s.status != "draft":
        locked = {"questions", "opens_at", "min_results", "course_name", "semester"} & fields_set
        if locked:
            raise Conflict("게시된 설문의 문항·시작일·최소 응답 수는 바꿀 수 없습니다. 복제해서 새 버전을 만드세요",
                           code="survey_locked")
        if s.status == "closed" and "closes_at" in fields_set:
            raise Conflict("종료된 설문의 마감일은 바꿀 수 없습니다")
    if title is not None:
        if not title.strip():
            raise BadRequest("제목이 필요합니다")
        s.title = title.strip()[:200]
    if description is not None:
        s.description = description[:5000]
    if course_name is not None:
        s.course_name = course_name.strip()[:120]
    if semester is not None:
        s.semester = semester.strip()[:40]
    if "opens_at" in fields_set:
        s.opens_at = opens_at
    if "closes_at" in fields_set:
        s.closes_at = closes_at
    if min_results is not None:
        if min_results < 1 or min_results > 50:
            raise BadRequest("최소 응답 수는 1~50입니다")
        s.min_results = min_results
    _check_window(s.opens_at, s.closes_at)
    if questions is not None:
        repo.replace_questions(s, _build_questions(validate_questions(questions)))
    audit_repo.add(db, actor.id, "survey.update", "survey", s.id, {"fields": sorted(fields_set)})
    db.commit()
    db.refresh(s)
    return s


def publish(db: Session, actor: User, survey_id: int, now: datetime | None = None) -> Survey:
    now = now or utcnow()
    s = _get(db, survey_id, lock=True)
    if s.status != "draft":
        raise Conflict("초안 상태의 설문만 게시할 수 있습니다")
    if not s.questions:
        raise BadRequest("문항이 최소 1개 필요합니다")
    validate_questions([QuestionInput(q.qtype, q.title, q.required, q.options) for q in s.questions])
    if s.closes_at and s.closes_at <= now:
        raise BadRequest("마감일이 이미 지났습니다")
    s.status = "published"
    if s.opens_at is None:
        s.opens_at = now
    audit_repo.add(db, actor.id, "survey.publish", "survey", s.id)
    db.commit()
    return s


def close(db: Session, actor: User, survey_id: int) -> Survey:
    s = _get(db, survey_id, lock=True)
    if s.status != "published":
        raise Conflict("게시 중인 설문만 종료할 수 있습니다")
    s.status = "closed"
    audit_repo.add(db, actor.id, "survey.close", "survey", s.id)
    db.commit()
    return s


def duplicate(db: Session, actor: User, survey_id: int) -> Survey:
    src = _get(db, survey_id)
    s = Survey(title=f"{src.title} (복제)"[:200], description=src.description, min_results=src.min_results,
               source_survey_id=src.id, created_by_id=actor.id,
               course_name=src.course_name, semester=src.semester)
    s.questions = [Question(position=q.position, qtype=q.qtype, title=q.title, required=q.required,
                            options=list(q.options or [])) for q in src.questions]
    db.add(s)
    db.flush()
    audit_repo.add(db, actor.id, "survey.duplicate", "survey", s.id, {"source": src.id})
    db.commit()
    return s


def delete_draft(db: Session, actor: User, survey_id: int) -> None:
    s = _get(db, survey_id, lock=True)
    if s.status != "draft":
        raise Conflict("초안만 삭제할 수 있습니다. 게시된 설문은 종료하세요")
    audit_repo.add(db, actor.id, "survey.delete", "survey", s.id, {"title": s.title})
    db.delete(s)
    db.commit()


# ───────── 학생 ─────────

def list_for_student(db: Session, student: User, now: datetime | None = None) -> list[tuple[Survey, bool, bool]]:
    now = now or utcnow()
    done = repo.participated_survey_ids(db, student.id)  # 본인 참여 여부는 본인에게만 보인다
    return [(s, s.id in done, is_open(s, now)) for s in repo.list_by_status(db, ("published", "closed"))]


def get_for_student(db: Session, student: User, survey_id: int, now: datetime | None = None) -> tuple[Survey, bool]:
    now = now or utcnow()
    s = _get(db, survey_id)
    if s.status == "draft":
        raise NotFound("설문을 찾을 수 없습니다")
    return s, s.id in repo.participated_survey_ids(db, student.id)


def _validate_answer(q: Question, value: object) -> object | None:
    empty = value is None or value == "" or value == []
    if empty:
        if q.required:
            raise BadRequest(f"필수 문항에 답해 주세요: {q.title[:30]}")
        return None
    if q.qtype in TEXT_LIMITS:
        if not isinstance(value, str):
            raise BadRequest("텍스트 응답이 올바르지 않습니다")
        v = value.strip()
        if len(v) > TEXT_LIMITS[q.qtype]:
            raise BadRequest(f"응답은 {TEXT_LIMITS[q.qtype]}자 이하여야 합니다")
        if not v and q.required:
            raise BadRequest(f"필수 문항에 답해 주세요: {q.title[:30]}")
        return v or None
    if q.qtype in ("single", "dropdown"):
        if not isinstance(value, str) or value not in q.options:
            raise BadRequest("선택지에 없는 값입니다")
        return value
    if q.qtype == "multi":
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            raise BadRequest("복수 선택 응답이 올바르지 않습니다")
        if len(set(value)) != len(value) or not set(value) <= set(q.options):
            raise BadRequest("선택지에 없는 값이 있습니다")
        return [o for o in q.options if o in value]  # 선택지 순서로 정규화
    if q.qtype == "scale5":
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            raise BadRequest("척도는 1~5 사이 정수입니다")
        return value
    raise BadRequest("알 수 없는 문항 유형")


def submit(db: Session, student: User, survey_id: int, answers: dict[str, object],
           now: datetime | None = None) -> None:
    """참여 기록과 응답을 한 트랜잭션에 넣되, 둘 사이에 어떤 연결 값도 저장하지 않는다."""
    now = now or utcnow()
    s = _get(db, survey_id)
    if not is_open(s, now):
        raise Conflict("응답 기간이 아닙니다", code="survey_closed")
    by_id = {str(q.id): q for q in s.questions}
    unknown = set(answers) - set(by_id)
    if unknown:
        raise BadRequest("설문에 없는 문항이 포함되어 있습니다")
    cleaned = [(q, _validate_answer(q, answers.get(key))) for key, q in by_id.items()]
    try:
        db.add(Participation(survey_id=s.id, user_id=student.id))
        db.flush()
        resp = Response(id=str(uuid.uuid4()), survey_id=s.id)
        db.add(resp)
        db.flush()
        for q, v in cleaned:
            if v is not None:
                db.add(Answer(id=str(uuid.uuid4()), response_id=resp.id, question_id=q.id, value=v))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("이미 참여한 설문입니다", code="already_participated") from exc


# ───────── 결과 ─────────

def results(db: Session, survey_id: int, rng: random.Random | None = None) -> dict:
    s = _get(db, survey_id)
    n = repo.response_count(db, s.id)
    base = {"survey_id": s.id, "title": s.title, "status": s.status, "response_count": n,
            "min_results": s.min_results}
    if n < s.min_results:
        # 소수 응답은 개인 식별 위험 → 집계·원문 모두 숨김
        return {**base, "hidden": True, "questions": []}
    rng = rng or random.SystemRandom()
    answers = repo.answers_for(db, s.id)
    by_q: dict[int, list] = {}
    for a in answers:
        by_q.setdefault(a.question_id, []).append(a.value)
    out = []
    for q in s.questions:
        vals = by_q.get(q.id, [])
        item: dict = {"id": q.id, "qtype": q.qtype, "title": q.title, "answered": len(vals)}
        if q.qtype in ("single", "dropdown"):
            c = Counter(vals)
            item["counts"] = [{"option": o, "count": c.get(o, 0)} for o in q.options]
        elif q.qtype == "multi":
            c = Counter(x for v in vals for x in v)
            item["counts"] = [{"option": o, "count": c.get(o, 0)} for o in q.options]
        elif q.qtype == "scale5":
            c = Counter(vals)
            item["counts"] = [{"option": str(i), "count": c.get(i, 0)} for i in range(1, 6)]
            item["average"] = round(sum(vals) / len(vals), 2) if vals else None
        else:
            texts = list(vals)
            rng.shuffle(texts)  # 저장 순서와 무관하게 섞어서 보여준다
            item["texts"] = texts
        out.append(item)
    return {**base, "hidden": False, "questions": out}


def export_rows(db: Session, survey_id: int, rng: random.Random | None = None):
    s = _get(db, survey_id)
    n = repo.response_count(db, s.id)
    if n < s.min_results:
        raise Conflict(f"응답이 {s.min_results}건 이상일 때 내보낼 수 있습니다", code="below_threshold")
    rng = rng or random.SystemRandom()
    rows: dict[str, dict[int, object]] = {}
    for a in repo.answers_for(db, s.id):
        rows.setdefault(a.response_id, {})[a.question_id] = a.value
    header = [q.title for q in s.questions]
    data = []
    for answers in rows.values():
        row = []
        for q in s.questions:
            v = answers.get(q.id)
            row.append(", ".join(v) if isinstance(v, list) else ("" if v is None else v))
        data.append(row)
    rng.shuffle(data)
    summary = []
    for q in results(db, survey_id, rng)["questions"]:
        for c in q.get("counts", []):
            summary.append([q["title"], c["option"], c["count"]])
        if q.get("average") is not None:
            summary.append([q["title"], "평균", q["average"]])
    return s, header, data, summary


def get(db: Session, survey_id: int) -> Survey:
    return _get(db, survey_id)
