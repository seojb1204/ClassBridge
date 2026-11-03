"""관리자 전용: 사용자·역할, 운영 설정, 감사 기록."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.permissions import P
from app.db import get_db
from app.repositories import audit as audit_repo
from app.repositories import users as users_repo
from app.schemas.users import ActiveChangeIn, AuditOut, RoleChangeIn, UserOut
from app.services import settings_service, user_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
def list_users(role: str | None = None, q: str | None = None,
               p: Principal = Depends(require(P.USER_MANAGE)), db: Session = Depends(get_db)):
    return users_repo.list_users(db, role, q)


@router.put("/users/{user_id}/role", response_model=UserOut)
def change_role(user_id: int, body: RoleChangeIn,
                p: Principal = Depends(require(P.ROLE_MANAGE)), db: Session = Depends(get_db)):
    return user_service.change_role(db, p.user, user_id, body.role)


@router.put("/users/{user_id}/active", response_model=UserOut)
def change_active(user_id: int, body: ActiveChangeIn,
                  p: Principal = Depends(require(P.USER_MANAGE)), db: Session = Depends(get_db)):
    return user_service.set_active(db, p.user, user_id, body.is_active)


@router.get("/settings")
def get_settings(p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return {"values": settings_service.get_settings(db), "specs": settings_service.describe()}


@router.put("/settings")
def put_settings(changes: dict = Body(...),
                 p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return {"values": settings_service.update_settings(db, p.id, changes)}


@router.get("/audit", response_model=list[AuditOut])
def audit(limit: int = 100, offset: int = 0, action: str | None = None,
          p: Principal = Depends(require(P.AUDIT_VIEW)), db: Session = Depends(get_db)):
    return audit_repo.list_logs(db, min(max(limit, 1), 500), max(offset, 0), action)
