from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Suggestion


def add(db: Session, s: Suggestion) -> None:
    db.add(s)


def get(db: Session, sid: str) -> Suggestion | None:
    return db.get(Suggestion, sid)


def search(db: Session, status: str | None, category: str | None, limit: int, offset: int,
           *, trash: bool = False, public_only: bool = False, query: str = "", order: str = "newest") -> list[Suggestion]:
    # 같은 날짜 안에서는 정렬 기준이 없으므로 id(UUID) 순 → 제출 순서가 드러나지 않는다
    date_order = Suggestion.submitted_on.asc() if order == "oldest" else Suggestion.submitted_on.desc()
    stmt = select(Suggestion).order_by(date_order, Suggestion.id).limit(limit).offset(offset)
    if query.strip():
        stmt = stmt.where(Suggestion.content.contains(query.strip(), autoescape=True))
    stmt = stmt.where(Suggestion.deleted_on.is_not(None) if trash else Suggestion.deleted_on.is_(None))
    if public_only:
        stmt = stmt.where(Suggestion.is_public.is_(True))
    if status:
        stmt = stmt.where(Suggestion.status == status)
    if category:
        stmt = stmt.where(Suggestion.category == category)
    return list(db.execute(stmt).scalars())


def all_contents(db: Session, status: str | None = None) -> list[Suggestion]:
    stmt = select(Suggestion).where(Suggestion.deleted_on.is_(None)).order_by(Suggestion.id)
    if status:
        stmt = stmt.where(Suggestion.status == status)
    return list(db.execute(stmt).scalars())


def counts_by(db: Session, column) -> dict[str, int]:
    stmt = select(column, func.count()).where(Suggestion.deleted_on.is_(None)).group_by(column)
    return {k: n for k, n in db.execute(stmt).all()}
