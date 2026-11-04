"""상담 시간·예약 API."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.permissions import P
from app.db import get_db
from app.repositories import bookings as repo
from app.repositories import users as users_repo
from app.schemas.bookings import (
    BlackoutIn,
    BlackoutOut,
    BookingCancelIn,
    BookingCreateIn,
    BookingRescheduleIn,
    EventOut,
    MyBookingOut,
    NoteIn,
    OutcomeIn,
    SlotCancelIn,
    SlotCreateIn,
    SlotOut,
    SlotReplaceIn,
    SlotUpdateIn,
    ConsultationNotesPage,
    StaffBookingOut,
    StaffOverviewOut,
)
from app.services import booking_service as svc
from app.services import staff_insights as insights_svc
from app.services.settings_service import get_settings

router = APIRouter(prefix="/api", tags=["bookings"])


def _staff_out(b, u) -> StaffBookingOut:
    base = MyBookingOut.model_validate(b).model_dump()
    return StaffBookingOut(**base, student_id=u.id, student_name=u.name, student_email=u.email,
                           professor_note=b.professor_note)


def _student(db: Session, b):
    return users_repo.get(db, b.student_id)


def _out(p: Principal, db: Session, b):
    if p.can(P.BOOKING_MANAGE):
        return _staff_out(b, _student(db, b))
    return MyBookingOut.model_validate(b)


# ── 공개하는 예약 정책 (로그인 사용자만) ──
@router.get("/booking-policy")
def booking_policy(p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    settings = get_settings(db)
    return {k: settings[k] for k in ("booking_window_days", "booking_deadline_hours",
                                     "cancel_deadline_hours")}


# ── 상담 시간 ──
@router.get("/slots", response_model=list[SlotOut])
def list_slots(start: date = Query(...), days: int = Query(7, ge=1, le=62),
               p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    s, e = svc.kst_range(start, days)
    return [SlotOut(id=v.slot.id, start_at=v.slot.start_at, end_at=v.slot.end_at, kind=v.slot.kind,
                    capacity=v.slot.capacity, remaining=v.remaining, status=v.slot.status,
                    location=v.slot.location, note=v.slot.note, mine=v.mine, bookable=v.bookable,
                    reason=v.reason)
            for v in svc.list_slots_for(db, p.user, s, e)]


@router.post("/slots", status_code=201)
def create_slots(body: SlotCreateIn, p: Principal = Depends(require(P.SLOT_MANAGE)),
                 db: Session = Depends(get_db)):
    return svc.create_slots(db, p.user, svc.SlotSpec(**body.model_dump()))


@router.post("/slots/preview")
def preview_slots(body: SlotCreateIn, p: Principal = Depends(require(P.SLOT_MANAGE)),
                  db: Session = Depends(get_db)):
    return svc.preview_slots(db, p.user, svc.SlotSpec(**body.model_dump()))


@router.post("/slots/replace")
def replace_unbooked_slots(body: SlotReplaceIn, p: Principal = Depends(require(P.SLOT_MANAGE)),
                           db: Session = Depends(get_db)):
    return svc.replace_unbooked_slots(db, p.user,
                                     svc.SlotSpec(**body.model_dump(exclude={"expected_overlap_ids"})),
                                     body.expected_overlap_ids)


@router.patch("/slots/{slot_id}")
def update_slot(slot_id: int, body: SlotUpdateIn, p: Principal = Depends(require(P.SLOT_MANAGE)),
                db: Session = Depends(get_db)):
    s = svc.update_slot(db, p.user, slot_id, **body.model_dump(exclude_unset=True))
    return {"id": s.id, "capacity": s.capacity, "kind": s.kind, "booked_count": s.booked_count}


@router.post("/slots/{slot_id}/cancel")
def cancel_slot(slot_id: int, body: SlotCancelIn, p: Principal = Depends(require(P.SLOT_MANAGE)),
                db: Session = Depends(get_db)):
    return svc.cancel_slot(db, p.user, slot_id, body.force, body.reason)


@router.get("/blackouts", response_model=list[BlackoutOut])
def list_blackouts(p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    return repo.blackout_days(db)


@router.post("/blackouts", response_model=BlackoutOut, status_code=201)
def add_blackout(body: BlackoutIn, p: Principal = Depends(require(P.SLOT_MANAGE)),
                 db: Session = Depends(get_db)):
    return svc.add_blackout(db, p.user, body.day, body.reason)


@router.delete("/blackouts/{blackout_id}", status_code=204)
def remove_blackout(blackout_id: int, p: Principal = Depends(require(P.SLOT_MANAGE)),
                    db: Session = Depends(get_db)):
    svc.remove_blackout(db, p.user, blackout_id)


# ── 예약 (학생 본인) ──
@router.get("/bookings/mine", response_model=list[MyBookingOut])
def my_bookings(p: Principal = Depends(require(P.BOOKING_SELF)), db: Session = Depends(get_db)):
    return svc.my_bookings(db, p.user)


@router.post("/bookings", status_code=201)
def create_booking(body: BookingCreateIn, p: Principal = Depends(require(P.SLOT_VIEW)),
                   db: Session = Depends(get_db)):
    # 본인/대리 예약 권한은 서비스에서 판정 (student_id 지정은 교수자·관리자만)
    return _out(p, db, svc.book(db, p.user, body.slot_id, body.student_id, body.topic,
                                applicant_name=body.applicant_name, student_number=body.student_number,
                                grade=body.grade, consultation_type=body.consultation_type,
                                consultation_mode=body.consultation_mode))


@router.post("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, body: BookingCancelIn, p: Principal = Depends(require(P.SLOT_VIEW)),
                   db: Session = Depends(get_db)):
    return _out(p, db, svc.cancel(db, p.user, booking_id, body.reason))


@router.post("/bookings/{booking_id}/reschedule")
def reschedule_booking(booking_id: int, body: BookingRescheduleIn,
                       p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    return _out(p, db, svc.reschedule(db, p.user, booking_id, body.new_slot_id, body.reason))


# ── 상담 정보 (교수자·관리자, 읽기 전용) ──
@router.get("/staff/overview", response_model=StaffOverviewOut)
def staff_overview(days: int = Query(90, ge=1, le=365),
                   p: Principal = Depends(require(P.BOOKING_MANAGE)),
                   db: Session = Depends(get_db)):
    return insights_svc.overview(db, days)


@router.get("/staff/notes", response_model=ConsultationNotesPage)
def staff_notes(q: str = Query("", max_length=80),
                limit: int = Query(20, ge=1, le=50),
                offset: int = Query(0, ge=0, le=100000),
                p: Principal = Depends(require(P.CONSULT_NOTE)),
                db: Session = Depends(get_db)):
    return insights_svc.notes(db, q, limit, offset)


# ── 예약 관리 (교수자·관리자) ──
@router.get("/bookings", response_model=list[StaffBookingOut])
def search_bookings(start: date | None = None, days: int = Query(31, ge=1, le=370),
                    status: str | None = None,
                    p: Principal = Depends(require(P.BOOKING_MANAGE)), db: Session = Depends(get_db)):
    s, e = svc.kst_range(start, days) if start else (None, None)
    return [_staff_out(b, u) for b, u in svc.search_bookings(db, s, e, status)]


@router.post("/bookings/{booking_id}/outcome", response_model=StaffBookingOut)
def set_outcome(booking_id: int, body: OutcomeIn, p: Principal = Depends(require(P.BOOKING_MANAGE)),
                db: Session = Depends(get_db)):
    b = svc.set_outcome(db, p.user, booking_id, body.outcome)
    return _staff_out(b, _student(db, b))


@router.put("/bookings/{booking_id}/note", response_model=StaffBookingOut)
def set_note(booking_id: int, body: NoteIn, p: Principal = Depends(require(P.CONSULT_NOTE)),
             db: Session = Depends(get_db)):
    b = svc.set_note(db, p.user, booking_id, body.note)
    return _staff_out(b, _student(db, b))


@router.get("/bookings/{booking_id}/history", response_model=list[EventOut])
def history(booking_id: int, p: Principal = Depends(require(P.BOOKING_MANAGE)),
            db: Session = Depends(get_db)):
    return svc.booking_history(db, p.user, booking_id)


@router.get("/students")
def list_students(q: str | None = None, p: Principal = Depends(require(P.BOOKING_MANAGE)),
                  db: Session = Depends(get_db)):
    """대리 예약용 학생 목록 (활성 학생의 이름·이메일만)."""
    return [{"id": u.id, "name": u.name, "email": u.email}
            for u in users_repo.list_users(db, role="student", q=q) if u.is_active]
