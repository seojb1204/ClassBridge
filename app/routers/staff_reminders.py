"""Administrator-only private reminder scheduling. No email delivery."""
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.permissions import P
from app.db import get_db
from app.models.staff_reminder import StaffReminder
from app.services import staff_reminders as svc

router = APIRouter(prefix='/api/admin/staff-reminders', tags=['admin'])


class Create(BaseModel):
    id: UUID
    recipient_id: int = Field(gt=0)
    message: str = Field(min_length=1, max_length=240)
    scheduled_at: AwareDatetime

    @field_validator('message')
    @classmethod
    def clean(cls, text):
        text = text.strip()
        if not text or any(ord(c) < 32 and c not in '\n\t' for c in text):
            raise ValueError('알림 내용을 확인하세요')
        return text


def output(row):
    return {key: getattr(row, key) for key in ('id', 'recipient_id', 'message', 'scheduled_at',
            'created_at', 'dispatched_at', 'cancelled_at')}


@router.post('', status_code=201)
def create(body: Create, p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return output(svc.create(db, str(body.id), body.recipient_id, body.message, body.scheduled_at, p.id))


@router.get('')
def listing(p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return [output(row) for row in db.scalars(select(StaffReminder).order_by(StaffReminder.created_at.desc()).limit(100))]


@router.put('/{identifier}/cancel')
def cancel(identifier: UUID, p: Principal = Depends(require(P.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return output(svc.cancel(db, str(identifier), p.id))
