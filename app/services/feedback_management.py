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



def trash_snapshot(db):
    # The confirmed set, not a later query, defines the scope of a bulk purge.
    ids = list(db.scalars(select(Suggestion.id).where(Suggestion.deleted_on.is_not(None))
                         .order_by(Suggestion.id).limit(10001)))
    if len(ids) > 10000:
        raise BadRequest("휴지통이 너무 큽니다. 일부를 정리한 뒤 다시 시도해 주세요")
    return {"ids": ids, "count": len(ids)}


def empty_suggestion_trash(db, actor, ids, confirmation):
    return _purge_trash_selection(db, actor, ids, confirmation, "suggestion.empty_trash")


def delete_selected_suggestion_trash(db, actor, ids, confirmation):
    if not ids:
        raise BadRequest("삭제할 건의를 선택해 주세요")
    return _purge_trash_selection(db, actor, ids, confirmation, "suggestion.delete_selected")


def _purge_trash_selection(db, actor, ids, confirmation, audit_action):
    if confirmation != "영구 삭제" or len(set(ids)) != len(ids):
        raise BadRequest("휴지통 삭제 대상과 확인을 다시 확인해 주세요")
    rows = list(db.scalars(select(Suggestion).where(Suggestion.id.in_(ids))
                          .order_by(Suggestion.id).with_for_update()))
    if len(rows) != len(ids) or any(row.deleted_on is None for row in rows):
        raise Conflict("휴지통 내용이 변경되었습니다. 다시 확인해 주세요")
    if not rows:
        return {"deleted": 0}
    db.execute(delete(SuggestionReply).where(SuggestionReply.suggestion_id.in_(ids)))
    db.execute(delete(Suggestion).where(Suggestion.id.in_(ids)))
    # No contents or anonymous-author data are retained in the audit log.
    audit_repo.add(db, actor.id, audit_action, "suggestion", detail={"count": len(rows)})
    db.commit()
    return {"deleted": len(rows)}

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
