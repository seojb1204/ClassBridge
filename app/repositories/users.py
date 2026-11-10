from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User


def get(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def get_for_update(db: Session, user_id: int) -> User | None:
    return db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()


def get_by_sub(db: Session, sub: str) -> User | None:
    return db.execute(select(User).where(User.google_sub == sub)).scalar_one_or_none()


def get_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def list_users(db: Session, role: str | None = None, q: str | None = None,
               *, recent_first: bool = False) -> list[User]:
    first = User.last_login_at.desc().nulls_last() if recent_first else User.role.desc()
    stmt = select(User).order_by(first, User.name, User.id)
    if role:
        stmt = stmt.where(User.role == role)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.name).like(like))
    return list(db.execute(stmt).scalars())


def lock_active_admins(db: Session) -> list[User]:
    """활성 관리자 행을 잠근다 (PostgreSQL). 마지막 관리자 강등 경쟁 상태 방지."""
    stmt = (
        select(User)
        .where(User.role == "admin", User.is_active.is_(True))
        .order_by(User.id)
        .with_for_update()
    )
    return list(db.execute(stmt).scalars())


def count_active_admins(db: Session) -> int:
    return db.execute(
        select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))
    ).scalar_one()
