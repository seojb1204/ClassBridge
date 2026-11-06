"""Staff lifecycle actions; no anonymous author identity is retained."""
from uuid import uuid4

from sqlalchemy import delete, select, update

from app.core.errors import BadRequest, Conflict, NotFound
from app.db import utcnow
from app.models import Answer, Participation, Response, Survey
from app.models.suggestion import Suggestion, SuggestionReply
from app.repositories import audit as audit_repo
from app.repositories import surveys as survey_repo
from app.services.suggestion_service import clean_content
from app.timeutil import kst_date


def suggestion(db, sid, *, trash=False):
    item = db.execute(select(Suggestion).where(Suggestion.id == sid).with_for_update()).scalar_one_or_none()
    if item is None or (item.deleted_on is not None) != trash:
        raise NotFound("건의를 찾을 수 없습니다")
    return item


def manage_suggestion(db, actor, sid, action, confirmation=""):
    item = suggestion(db, sid, trash=action in ("restore", "purge"))
    if action == "trash":
        item.deleted_on = kst_date(utcnow())
    elif action == "restore":
        item.deleted_on = None
    elif action == "purge":
        if confirmation != "영구 삭제":
            raise BadRequest("영구 삭제 확인이 필요합니다")
        db.execute(delete(SuggestionReply).where(SuggestionReply.suggestion_id == sid))
        db.delete(item)
    audit_repo.add(db, actor.id, f"suggestion.{action}", "suggestion", sid)
    db.commit()


def reply(db, actor, sid, content):
    item = suggestion(db, sid)
    result = SuggestionReply(id=str(uuid4()), suggestion_id=sid,
                             content=clean_content(content), created_on=kst_date(utcnow()))
    db.add(result)
    item.status = "reviewed"
    audit_repo.add(db, actor.id, "suggestion.reply", "suggestion", sid)
    db.commit()
    return result


def manage_survey(db, actor, sid, action, confirmation="", expected_count=None):
    item = survey_repo.get(db, sid, lock=True, include_deleted=True)
    if item is None or (item.deleted_at is not None) != (action in ("restore", "purge")):
        raise NotFound("설문을 찾을 수 없습니다")
    if action == "trash":
        if item.status == "published":
            item.status = "closed"
        item.deleted_at = utcnow()
    elif action == "restore":
        item.deleted_at = None
    elif action == "purge":
        count = survey_repo.response_count(db, sid)
        if confirmation != "영구 삭제" or expected_count != count:
            raise Conflict("삭제할 응답 수를 다시 확인해 주세요")
        ids = select(Response.id).where(Response.survey_id == sid)
        db.execute(delete(Answer).where(Answer.response_id.in_(ids)))
        db.execute(delete(Response).where(Response.survey_id == sid))
        db.execute(delete(Participation).where(Participation.survey_id == sid))
        db.execute(update(Survey).where(Survey.source_survey_id == sid).values(source_survey_id=None))
        db.delete(item)
    audit_repo.add(db, actor.id, f"survey.{action}", "survey", sid)
    db.commit()
