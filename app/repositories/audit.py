from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def add(db: Session, actor_id: int | None, action: str, target_type: str = "",
        target_id: str | int = "", detail: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type,
                    target_id=str(target_id), detail=detail or {}))


def list_logs(db: Session, limit: int = 100, offset: int = 0, action: str | None = None) -> list[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list(db.execute(stmt).scalars())
