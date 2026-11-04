"""상담 시간 관리·예약 업무 규칙.

정원·1인 1예약 보장 방식:
- 정원: try_take_seat()의 조건부 UPDATE + CHECK(booked_count <= capacity)
- 1인 1예약: 부분 유니크 인덱스(uq_bookings_one_active_per_student)
둘 다 DB가 최종 판정하므로 애플리케이션 검사를 우회한 동시 요청도 막힌다.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Callable, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, BadRequest, Conflict, Forbidden, NotFound
from app.core.permissions import P, has_permission
from app.db import utcnow
from app.models import Blackout, Booking, Slot, User
from app.repositories import audit as audit_repo
from app.repositories import bookings as repo
from app.repositories import users as users_repo
from app.services import booking_policy as policy_mod
from app.services.booking_policy import Policy
from app.services.settings_service import get_settings
from app.timeutil import KST, kst_date, kst_to_utc

T = TypeVar("T")


def _is_staff(user: User) -> bool:
    return has_permission(user.role, P.BOOKING_MANAGE)


def _policy(db: Session) -> Policy:
    return Policy.from_settings(get_settings(db))


def _atomic(db: Session, fn: Callable[[], T]) -> T:
    """fn 실행 후 커밋. 어떤 실패든 전체 롤백 → 기존 예약이 사라지는 부분 실패가 없다."""
    try:
        result = fn()
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        msg = str(exc.orig).lower()
        # PostgreSQL exclusion constraint rejects overlapping consultation slots atomically.
        if getattr(exc.orig, "sqlstate", None) == "23P01" or "ex_slots_no_overlap_open" in msg:
            raise Conflict("다른 상담 시간과 겹칩니다", code="slot_overlap") from exc
        if "one_active_per_student" in msg or ("unique" in msg and "bookings" in msg and "student_id" in msg):
            raise Conflict("이미 진행 중인 상담 예약이 있습니다. 기존 예약을 취소하거나 변경하세요",
                           code="active_booking_exists") from exc
        if "booked_range" in msg or "check" in msg:
            raise Conflict("정원 조건을 만족하지 않습니다", code="capacity") from exc
        raise Conflict("데이터 충돌이 발생했습니다. 다시 시도하세요") from exc
    except AppError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


# ───────────── 조회 ─────────────

@dataclass
class SlotView:
    slot: Slot
    remaining: int
    mine: bool
    bookable: bool
    reason: str


def list_slots_for(db: Session, viewer: User, start: datetime, end: datetime,
                   now: datetime | None = None) -> list[SlotView]:
    now = now or utcnow()
    if end - start > timedelta(days=62):
        raise BadRequest("조회 기간은 최대 62일입니다")
    staff = _is_staff(viewer)
    slots = repo.list_slots(db, start, end, include_cancelled=staff)
    pol = _policy(db)
    mine_active = None if staff else repo.active_booking_of(db, viewer.id)
    blackouts = {b.day for b in repo.blackout_days(db)}
    views = []
    for s in slots:
        remaining = max(s.capacity - s.booked_count, 0)
        mine = bool(mine_active and mine_active.slot_id == s.id)
        reason = ""
        if s.status != "open":
            reason = "취소된 시간"
        elif remaining == 0:
            reason = "마감"
        elif kst_date(s.start_at) in blackouts:
            reason = "상담 불가일"
        else:
            try:
                policy_mod.check_student_booking_time(s.start_at, now, pol)
            except Conflict as e:
                reason = e.message
        views.append(SlotView(s, remaining, mine, reason == "" and not mine, reason))
    return views


def my_bookings(db: Session, student: User) -> list[Booking]:
    return repo.bookings_of_student(db, student.id)


def search_bookings(db: Session, start: datetime | None, end: datetime | None, status: str | None):
    return repo.search_bookings(db, start, end, status)


def _visible_booking(db: Session, actor: User, booking_id: int, lock: bool = False) -> Booking:
    b = repo.get_booking(db, booking_id, lock=lock)
    # 남의 예약은 '없는 것'으로 응답해 존재 여부도 노출하지 않는다
    if b is None or (not _is_staff(actor) and b.student_id != actor.id):
        raise NotFound("예약을 찾을 수 없습니다")
    return b


def booking_history(db: Session, actor: User, booking_id: int):
    _visible_booking(db, actor, booking_id)
    return repo.events_for(db, booking_id)


# ───────────── 교수자: 상담 시간 관리 ─────────────

@dataclass
class SlotSpec:
    start_date: date
    start_time: time
    end_time: time
    duration_minutes: int
    kind: str = "individual"
    capacity: int = 1
    break_minutes: int | None = None
    repeat_weeks: int = 1
    weekdays: list[int] | None = None
    location: str = ""
    note: str = ""


def _validate_kind_capacity(kind: str, capacity: int) -> None:
    if kind not in ("individual", "group"):
        raise BadRequest("상담 유형이 올바르지 않습니다")
    if kind == "individual" and capacity != 1:
        raise BadRequest("개인 상담의 정원은 1명입니다")
    if kind == "group" and not (2 <= capacity <= 100):
        raise BadRequest("단체 상담 정원은 2~100명입니다")


def _planned_blocks(db: Session, spec: SlotSpec, now: datetime) -> tuple[list[tuple[datetime, datetime]], list[str]]:
    """One source of truth for previews and registrations."""
    _validate_kind_capacity(spec.kind, spec.capacity)
    brk = spec.break_minutes if spec.break_minutes is not None else get_settings(db)["default_break_minutes"]
    days = policy_mod.expand_days(spec.start_date, spec.weekdays, spec.repeat_weeks)
    blackouts = {b.day for b in repo.blackout_days(db, min(days), max(days))} if days else set()
    usable = [d for d in days if d not in blackouts]
    skipped = sorted(d.isoformat() for d in set(days) & blackouts)
    if not usable:
        raise Conflict("선택한 날짜가 모두 상담 불가일입니다")
    blocks = policy_mod.generate_blocks(usable, spec.start_time, spec.end_time,
                                        spec.duration_minutes, brk)
    blocks = [b for b in blocks if b[0] > now]
    if not blocks:
        raise BadRequest("미래 시간만 등록할 수 있습니다")
    return blocks, skipped


def _overlapping_by_id(db: Session, blocks: list[tuple[datetime, datetime]]) -> dict[int, Slot]:
    conflicts: dict[int, Slot] = {}
    for st, en in blocks:
        for existing in repo.overlapping_open_slots(db, st, en):
            conflicts[existing.id] = existing
    return conflicts


def preview_slots(db: Session, actor: User, spec: SlotSpec, now: datetime | None = None) -> dict:
    if not _is_staff(actor):
        raise Forbidden("상담 시간 관리 권한이 없습니다")
    blocks, skipped = _planned_blocks(db, spec, now or utcnow())
    conflicts = _overlapping_by_id(db, blocks)
    protected = sorted(s.id for s in conflicts.values() if s.booked_count > 0)
    return {
        "created": len(blocks),
        "replaced": len(conflicts),
        "overlap_ids": sorted(conflicts),
        "protected_ids": protected,
        "planned_slots": [{"start_at":start.isoformat(), "end_at":end.isoformat()}
                          for start, end in blocks],
        "conflicting_slots": [
            {"id": row.id, "start_at": row.start_at.isoformat(),
             "end_at": row.end_at.isoformat(), "booked_count": row.booked_count}
            for row in sorted(conflicts.values(), key=lambda item: item.start_at)
        ],
        "skipped_blackout_days": skipped,
    }


def replace_unbooked_slots(db: Session, actor: User, spec: SlotSpec,
                            expected_overlap_ids: list[int], now: datetime | None = None) -> dict:
    """Replace only unbooked open slots; keep old cancelled records and all bookings.

    Explicit expected IDs make stale previews fail closed rather than unexpectedly
    changing a different slot. The database exclusion constraint is the final race guard.
    """
    if not _is_staff(actor):
        raise Forbidden("상담 시간 관리 권한이 없습니다")
    now = now or utcnow()
    blocks, skipped = _planned_blocks(db, spec, now)
    expected = sorted(set(expected_overlap_ids))

    def work():
        # Lock old rows in stable order and re-check within the transaction.
        conflicts = _overlapping_by_id(db, blocks)
        if sorted(conflicts) != expected:
            raise Conflict("상담 시간이 변경됐습니다. 미리보기를 다시 확인하세요",
                           code="slot_preview_stale")
        rows = [repo.get_slot(db, slot_id, lock=True) for slot_id in expected]
        if any(row is None or row.status != "open" or row.booked_count > 0
               or repo.active_bookings_for_slot(db, row.id) for row in rows):
            raise Conflict("이미 예약된 상담은 자동 교체할 수 없습니다", code="slot_has_bookings")
        for row in rows:
            row.status = "cancelled"
        db.flush()  # Release partial GiST exclusion before inserting replacements.
        series = uuid.uuid4().hex if len(blocks) > 1 else None
        created = []
        for st, en in blocks:
            obj = Slot(start_at=st, end_at=en, kind=spec.kind, capacity=spec.capacity,
                       location=spec.location[:200], note=spec.note[:500], series_id=series,
                       created_by_id=actor.id)
            db.add(obj)
            created.append(obj)
        db.flush()
        audit_repo.add(db, actor.id, "slot.replace_unbooked", "slot_series", series or created[0].id,
                       {"created": len(created), "replaced_ids": expected})
        return {"created": len(created), "replaced": len(rows),
                "slot_ids": [s.id for s in created], "skipped_blackout_days": skipped}

    return _atomic(db, work)


def create_slots(db: Session, actor: User, spec: SlotSpec, now: datetime | None = None) -> dict:
    now = now or utcnow()
    blocks, skipped = _planned_blocks(db, spec, now)
    conflicts = []
    for st, en in blocks:
        for other in repo.overlapping_open_slots(db, st, en):
            conflicts.append({"start_at": st.isoformat(), "existing_slot_id": other.id})
    if conflicts:
        raise Conflict(f"기존 상담 시간과 겹치는 시간이 {len(conflicts)}개 있습니다", code="slot_overlap")
    series = uuid.uuid4().hex if len(blocks) > 1 else None

    def work():
        created = []
        for st, en in blocks:
            s = Slot(start_at=st, end_at=en, kind=spec.kind, capacity=spec.capacity,
                     location=spec.location[:200], note=spec.note[:500], series_id=series,
                     created_by_id=actor.id)
            db.add(s)
            created.append(s)
        db.flush()
        audit_repo.add(db, actor.id, "slot.create", "slot_series", series or created[0].id,
                       {"count": len(created), "kind": spec.kind, "capacity": spec.capacity})
        return {"created": len(created), "skipped_blackout_days": skipped,
                "slot_ids": [s.id for s in created]}

    return _atomic(db, work)


def update_slot(db: Session, actor: User, slot_id: int, *, capacity: int | None = None,
                kind: str | None = None, location: str | None = None, note: str | None = None,
                start_at: datetime | None = None, end_at: datetime | None = None) -> Slot:
    def work():
        s = repo.get_slot(db, slot_id, lock=True)
        if s is None:
            raise NotFound("상담 시간을 찾을 수 없습니다")
        if s.status != "open":
            raise Conflict("취소된 상담 시간은 수정할 수 없습니다")
        new_kind = kind or s.kind
        new_cap = capacity if capacity is not None else (1 if new_kind == "individual" else s.capacity)
        if new_cap < s.booked_count:
            raise Conflict(f"현재 예약 인원({s.booked_count}명)보다 정원을 줄일 수 없습니다. "
                           "먼저 일부 예약을 조정하세요", code="capacity_below_booked")
        _validate_kind_capacity(new_kind, new_cap)
        if start_at or end_at:
            ns, ne = start_at or s.start_at, end_at or s.end_at
            if s.booked_count > 0:
                raise Conflict("예약이 있는 상담의 시간은 바꿀 수 없습니다. 예약을 변경한 뒤 수정하세요")
            if ne <= ns:
                raise BadRequest("종료 시각은 시작 시각보다 늦어야 합니다")
            if repo.overlapping_open_slots(db, ns, ne, exclude_id=s.id):
                raise Conflict("다른 상담 시간과 겹칩니다", code="slot_overlap")
            if repo.is_blackout(db, kst_date(ns)):
                raise Conflict("상담 불가일입니다")
            s.start_at, s.end_at = ns, ne
        s.kind, s.capacity = new_kind, new_cap
        if location is not None:
            s.location = location[:200]
        if note is not None:
            s.note = note[:500]
        audit_repo.add(db, actor.id, "slot.update", "slot", s.id,
                       {"capacity": s.capacity, "kind": s.kind})
        return s

    return _atomic(db, work)


def cancel_slot(db: Session, actor: User, slot_id: int, force: bool, reason: str) -> dict:
    def work():
        s = repo.get_slot(db, slot_id, lock=True)
        if s is None:
            raise NotFound("상담 시간을 찾을 수 없습니다")
        if s.status == "cancelled":
            return {"cancelled_bookings": 0}
        active = repo.active_bookings_for_slot(db, s.id)
        if active and not force:
            raise Conflict(f"예약된 학생이 {len(active)}명 있습니다. 예약을 함께 취소하려면 force를 지정하세요",
                           code="slot_has_bookings")
        if active and not reason.strip():
            raise BadRequest("예약이 있는 상담을 취소할 때는 사유가 필요합니다")
        for b in active:
            b.status = "cancelled"
            b.cancel_reason = f"상담 시간 취소: {reason}"[:500]
            repo.add_event(db, b.id, actor.id, "cancel_by_slot", reason)
        s.status = "cancelled"
        s.booked_count = 0
        audit_repo.add(db, actor.id, "slot.cancel", "slot", s.id,
                       {"cancelled_bookings": len(active), "reason": reason[:200]})
        return {"cancelled_bookings": len(active)}

    return _atomic(db, work)


def add_blackout(db: Session, actor: User, day: date, reason: str) -> Blackout:
    def work():
        start = kst_to_utc(day, time(0, 0))
        clash = repo.list_slots(db, start, start + timedelta(days=1), include_cancelled=False)
        if clash:
            raise Conflict(f"해당 날짜에 열린 상담 시간이 {len(clash)}개 있습니다. 먼저 취소하세요",
                           code="blackout_has_slots")
        if repo.is_blackout(db, day):
            raise Conflict("이미 등록된 상담 불가일입니다")
        b = Blackout(day=day, reason=reason[:200], created_by_id=actor.id)
        db.add(b)
        db.flush()
        audit_repo.add(db, actor.id, "blackout.add", "blackout", b.id, {"day": day.isoformat()})
        return b

    return _atomic(db, work)


def remove_blackout(db: Session, actor: User, blackout_id: int) -> None:
    def work():
        b = db.get(Blackout, blackout_id)
        if b is None:
            raise NotFound("상담 불가일을 찾을 수 없습니다")
        audit_repo.add(db, actor.id, "blackout.remove", "blackout", b.id, {"day": b.day.isoformat()})
        db.delete(b)

    _atomic(db, work)


# ───────────── 예약 ─────────────

def _resolve_student(db: Session, actor: User, student_id: int | None) -> User:
    if student_id is None or student_id == actor.id:
        if not has_permission(actor.role, P.BOOKING_SELF):
            raise Forbidden("본인 예약 권한이 없습니다")
        return actor
    if not _is_staff(actor):
        raise Forbidden("다른 학생의 예약을 만들 수 없습니다")
    target = users_repo.get(db, student_id)
    if target is None or target.role != "student" or not target.is_active:
        raise BadRequest("활성 학생 계정이 아닙니다")
    return target


def _check_slot_for(db: Session, actor: User, slot: Slot | None, now: datetime, pol: Policy) -> Slot:
    if slot is None or slot.status != "open":
        raise NotFound("예약 가능한 상담 시간이 아닙니다")
    if repo.is_blackout(db, kst_date(slot.start_at)):
        raise Conflict("상담 불가일입니다", code="blackout")
    if _is_staff(actor):
        if slot.start_at <= now:
            raise Conflict("이미 지난 상담 시간입니다", code="slot_past")
    else:
        policy_mod.check_student_booking_time(slot.start_at, now, pol)
    return slot


def book(db: Session, actor: User, slot_id: int, student_id: int | None = None,
         topic: str = "", now: datetime | None = None, *,
         applicant_name: str = "", student_number: str = "", grade: int | None = None,
         consultation_type: str = "other", consultation_mode: str = "in_person") -> Booking:
    now = now or utcnow()
    pol = _policy(db)
    student = _resolve_student(db, actor, student_id)

    def work():
        slot = _check_slot_for(db, actor, repo.get_slot(db, slot_id), now, pol)
        if repo.active_booking_of(db, student.id) is not None:
            raise Conflict("이미 진행 중인 상담 예약이 있습니다. 기존 예약을 취소하거나 변경하세요",
                           code="active_booking_exists")
        if not repo.try_take_seat(db, slot.id):
            raise Conflict("정원이 마감되었습니다", code="slot_full")
        b = Booking(slot_id=slot.id, student_id=student.id, topic=topic[:500], created_by_id=actor.id,
                    applicant_name=(applicant_name.strip() or student.name)[:100],
                    student_number=student_number.strip()[:30], grade=grade,
                    consultation_type=consultation_type, consultation_mode=consultation_mode)
        db.add(b)
        db.flush()  # 부분 유니크 인덱스 위반은 여기서 IntegrityError
        repo.add_event(db, b.id, actor.id, "book" if actor.id == student.id else "book_by_staff")
        if actor.id != student.id:
            audit_repo.add(db, actor.id, "booking.create_for_student", "booking", b.id,
                           {"student_id": student.id, "slot_id": slot.id})
        return b

    b = _atomic(db, work)
    db.refresh(b)
    return b


def cancel(db: Session, actor: User, booking_id: int, reason: str = "",
           now: datetime | None = None) -> Booking:
    now = now or utcnow()
    pol = _policy(db)
    staff = _is_staff(actor)

    def work():
        b = _visible_booking(db, actor, booking_id, lock=True)
        policy_mod.check_transition(b.status, "cancelled")
        if staff:
            if not reason.strip():
                raise BadRequest("교수자·관리자 취소에는 사유가 필요합니다")
        else:
            policy_mod.check_student_cancel_time(b.slot.start_at, now, pol)
        b.status = "cancelled"
        b.cancel_reason = reason[:500]
        repo.release_seat(db, b.slot_id)
        repo.add_event(db, b.id, actor.id, "cancel_by_staff" if staff else "cancel", reason)
        if staff:
            audit_repo.add(db, actor.id, "booking.cancel_by_staff", "booking", b.id,
                           {"student_id": b.student_id, "reason": reason[:200]})
        return b

    b = _atomic(db, work)
    db.refresh(b)
    return b


def reschedule(db: Session, actor: User, booking_id: int, new_slot_id: int, reason: str = "",
               now: datetime | None = None) -> Booking:
    """기존 취소 + 새 예약을 한 트랜잭션으로. 새 예약이 실패하면 기존 예약은 그대로 남는다."""
    now = now or utcnow()
    pol = _policy(db)
    staff = _is_staff(actor)

    def work():
        old = _visible_booking(db, actor, booking_id, lock=True)
        if old.status != "booked":
            raise Conflict("진행 중인 예약만 변경할 수 있습니다")
        if old.slot_id == new_slot_id:
            raise BadRequest("같은 상담 시간입니다")
        if staff and not reason.strip() and old.student_id != actor.id:
            raise BadRequest("교수자·관리자 변경에는 사유가 필요합니다")
        if not staff:
            policy_mod.check_student_cancel_time(old.slot.start_at, now, pol)
        new_slot = _check_slot_for(db, actor, repo.get_slot(db, new_slot_id), now, pol)

        old.status = "cancelled"
        old.cancel_reason = "예약 변경"
        repo.release_seat(db, old.slot_id)
        db.flush()  # 부분 인덱스에서 기존 활성 예약 해제
        if not repo.try_take_seat(db, new_slot.id):
            raise Conflict("변경하려는 시간의 정원이 마감되었습니다. 기존 예약은 유지됩니다", code="slot_full")
        nb = Booking(slot_id=new_slot.id, student_id=old.student_id, topic=old.topic,
                     created_by_id=actor.id, applicant_name=old.applicant_name,
                     student_number=old.student_number, grade=old.grade,
                     consultation_type=old.consultation_type, consultation_mode=old.consultation_mode)
        db.add(nb)
        db.flush()
        repo.add_event(db, old.id, actor.id, "rescheduled_from", f"→ booking {nb.id}")
        repo.add_event(db, nb.id, actor.id, "rescheduled_to", f"← booking {old.id}; {reason}")
        if staff:
            audit_repo.add(db, actor.id, "booking.reschedule_by_staff", "booking", nb.id,
                           {"from_booking": old.id, "student_id": old.student_id, "reason": reason[:200]})
        return nb

    nb = _atomic(db, work)
    db.refresh(nb)
    return nb


def set_outcome(db: Session, actor: User, booking_id: int, outcome: str,
                now: datetime | None = None) -> Booking:
    now = now or utcnow()
    if outcome not in ("completed", "no_show"):
        raise BadRequest("완료 또는 미참석만 지정할 수 있습니다")

    def work():
        b = _visible_booking(db, actor, booking_id, lock=True)
        if not _is_staff(actor):
            raise Forbidden("권한이 없습니다")
        if b.slot.start_at > now:
            raise Conflict("상담 시작 이후에 처리할 수 있습니다")
        policy_mod.check_transition(b.status, outcome)
        b.status = outcome
        repo.add_event(db, b.id, actor.id, outcome)
        return b

    b = _atomic(db, work)
    db.refresh(b)
    return b


def set_note(db: Session, actor: User, booking_id: int, note: str) -> Booking:
    if not has_permission(actor.role, P.CONSULT_NOTE):
        raise Forbidden("권한이 없습니다")
    if len(note) > 10000:
        raise BadRequest("상담 기록은 10000자 이하입니다")

    def work():
        b = _visible_booking(db, actor, booking_id, lock=True)
        b.professor_note = note
        repo.add_event(db, b.id, actor.id, "note_update")
        return b

    b = _atomic(db, work)
    db.refresh(b)
    return b


def kst_range(start_date: date, days: int) -> tuple[datetime, datetime]:
    start = datetime.combine(start_date, time(0, 0), tzinfo=KST)
    return start, start + timedelta(days=days)
