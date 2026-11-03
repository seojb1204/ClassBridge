"""익명 건의함.

- 작성자 ID·제출 시각·IP를 저장하지 않는다 (제출 날짜만).
- 제출 횟수 제한은 없지만, 메모리 기반 속도 제한으로 자동화된 폭주만 막는다.
  속도 제한 키는 사용자 ID의 키 해시이며, 제출 내용과 함께 저장되지 않는다.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotFound
from app.core.rate_limit import RateLimiter
from app.db import utcnow
from app.models import Suggestion, User
from app.models.suggestion import SUGGESTION_CATEGORIES
from app.repositories import suggestions as repo
from app.timeutil import kst_date

MAX_LEN = 2000
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
STATUSES = ("new", "reviewed", "archived")


def clean_content(raw: str) -> str:
    text = _CTRL.sub("", raw or "").strip()
    if not text:
        raise BadRequest("내용을 입력하세요")
    if len(text) > MAX_LEN:
        raise BadRequest(f"건의 내용은 {MAX_LEN}자 이하입니다")
    return text


def limiter_key(secret: str, user_id: int) -> str:
    return hmac.new(secret.encode(), f"sugg:{user_id}".encode(), hashlib.sha256).hexdigest()[:24]


def submit(db: Session, limiter: RateLimiter, secret: str, user: User, category: str, content: str,
           now: datetime | None = None) -> None:
    now = now or utcnow()
    if category not in SUGGESTION_CATEGORIES:
        raise BadRequest("건의 유형이 올바르지 않습니다")
    text = clean_content(content)
    limiter.hit(limiter_key(secret, user.id))
    repo.add(db, Suggestion(id=str(uuid.uuid4()), category=category, content=text,
                            submitted_on=kst_date(now)))
    db.commit()


def search(db: Session, status: str | None, category: str | None, limit: int = 100, offset: int = 0):
    if status and status not in STATUSES:
        raise BadRequest("상태 값이 올바르지 않습니다")
    return repo.search(db, status, category, min(max(limit, 1), 500), max(offset, 0))


def set_status(db: Session, suggestion_id: str, status: str) -> Suggestion:
    if status not in STATUSES:
        raise BadRequest("상태 값이 올바르지 않습니다")
    s = repo.get(db, suggestion_id)
    if s is None:
        raise NotFound("건의를 찾을 수 없습니다")
    s.status = status
    db.commit()
    return s


def stats(db: Session) -> dict:
    return {
        "by_category": repo.counts_by(db, Suggestion.category),
        "by_status": repo.counts_by(db, Suggestion.status),
        "total": sum(repo.counts_by(db, Suggestion.status).values()),
    }
