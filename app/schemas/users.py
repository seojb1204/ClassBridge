from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["student", "professor", "admin"]


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class MeOut(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    permissions: list[str]
    csrf_token: str
    features: dict[str, bool | str]


class RoleChangeIn(BaseModel):
    role: Role


class ActiveChangeIn(BaseModel):
    is_active: bool


class DevLoginIn(BaseModel):
    remember: bool = False
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(default="", max_length=100)


class AuditOut(BaseModel):
    id: int
    actor_id: int | None
    action: str
    target_type: str
    target_id: str
    detail: dict
    at: datetime

    model_config = {"from_attributes": True}
