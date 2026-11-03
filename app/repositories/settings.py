from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AppSetting


def get_all(db: Session) -> dict[str, object]:
    return {s.key: s.value for s in db.execute(select(AppSetting)).scalars()}


def put(db: Session, key: str, value: object) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
