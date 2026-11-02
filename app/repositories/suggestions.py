from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Suggestion


def add(db: Session, s: Suggestion) -> None:
    db.add(s)


def get(db: Session, sid: str) -> Suggestion | None:
    return db.get(Suggestion, sid)


def search(db: Session, status: str | None, category: str | None, limit: int, offset: int) -> list[Suggestion]:
    # 같은 날짜 안에서는 정렬 기준이 없으므로 id(UUID) 순 → 제출 순서가 드러나지 않는다
    stmt = select(Suggestion).order_by(Suggestion.submitted_on.desc(), Suggestion.id).limit(limit).offset(offset)
    if status:
        stmt = stmt.where(Suggestion.status == status)
    if category:
        stmt = stmt.where(Suggestion.category == category)
    return list(db.execute(stmt).scalars())


def all_contents(db: Session, status: str | None = None) -> list[Suggestion]:
    stmt = select(Suggestion).order_by(Suggestion.id)
    if status:
        stmt = stmt.where(Suggestion.status == status)
    return list(db.execute(stmt).scalars())


def counts_by(db: Session, column) -> dict[str, int]:
    return {k: n for k, n in db.execute(select(column, func.count()).group_by(column)).all()}
