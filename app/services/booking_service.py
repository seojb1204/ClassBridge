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
from types import SimpleNamespace
from typing import Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.errors import AppError, BadRequest, Conflict, Forbidden, NotFound
from app.core.permissions import P, has_permission
from app.db import utcnow
from app.models import Booking, Slot, User
from app.repositories import audit as audit_repo
from app.repositories import bookings as repo
from app.repositories import users as users_repo
from app.services import booking_policy as policy_mod
from app.services.booking_policy import Policy
from app.services.notifications import enqueue
from app.services.settings_service import get_settings
from app.timeutil import KST

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
    except OperationalError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) in ("40P01", "40001"):
            raise Conflict("다른 예약 작업과 겹쳤습니다. 기존 기록은 유지됩니다. 다시 시도해 주세요",
                           code="booking_concurrent_change") from None
        raise
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
    can_delete: bool = False


def list_slots_for(db: Session, viewer: User, start: datetime, end: datetime,
                   now: datetime | None = None) -> list[SlotView]:
    now = now or utcnow()
    if end - start > timedelta(days=62):
        raise BadRequest("조회 기간은 최대 62일입니다")
    staff = _is_staff(viewer)
    slots = repo.list_slots(db, start, end, include_cancelled=staff)
    history = repo.booked_slot_ids(db, [s.id for s in slots]) if staff else set()
    pol = _policy(db)
    mine_active = None if staff else repo.active_booking_of(db, viewer.id)
    views = []
    for s in slots:
        remaining = max(s.capacity - s.booked_count, 0)
        mine = bool(mine_active and mine_active.slot_id == s.id)
        reason = ""
        if s.status != "open":
            reason = "취소된 시간"
        elif remaining == 0:
            reason = "마감"
        else:
            try:
                policy_mod.check_student_booking_time(s.start_at, now, pol, enforce_window=mine_active is None)
            except Conflict as e:
                reason = e.message
        views.append(SlotView(s, remaining, mine, reason == "" and not mine, reason,
                              staff and s.status == "cancelled" and s.id not in history
                              and (viewer.role == "admin" or s.created_by_id == viewer.id)))
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


def _planned_blocks(db: Session, spec: SlotSpec, now: datetime) -> list[tuple[datetime, datetime]]:
    """One source of truth for previews and registrations."""
    _validate_kind_capacity(spec.kind, spec.capacity)
    brk = spec.break_minutes if spec.break_minutes is not None else get_settings(db)["default_break_minutes"]
    days = policy_mod.expand_days(spec.start_date, spec.weekdays, spec.repeat_weeks)
    blocks = policy_mod.generate_blocks(days, spec.start_time, spec.end_time,
                                        spec.duration_minutes, brk)
    blocks = [b for b in blocks if b[0] > now]
    if not blocks:
        raise BadRequest("미래 시간만 등록할 수 있습니다")
    return blocks


def _overlapping_by_id(db: Session, blocks: list[tuple[datetime, datetime]]) -> dict[int, Slot]:
    conflicts: dict[int, Slot] = {}
    for st, en in blocks:
        for existing in repo.overlapping_open_slots(db, st, en):
            conflicts[existing.id] = existing
    return conflicts


def preview_slots(db: Session, actor: User, spec: SlotSpec, now: datetime | None = None) -> dict:
    if not _is_staff(actor):
        raise Forbidden("상담 시간 관리 권한이 없습니다")
    blocks = _planned_blocks(db, spec, now or utcnow())
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
        "skipped_blackout_days": [],  # Legacy response key; availability now depends only on slots.
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
    blocks = _planned_blocks(db, spec, now)
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
                "slot_ids": [s.id for s in created], "skipped_blackout_days": []}

    return _atomic(db, work)


def create_slots(db: Session, actor: User, spec: SlotSpec, now: datetime | None = None) -> dict:
    now = now or utcnow()
    blocks = _planned_blocks(db, spec, now)
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
        return {"created": len(created), "skipped_blackout_days": [],
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
            s.start_at, s.end_at = ns, ne
        changed_info = (new_kind != s.kind or (location is not None and location != s.location)
                        or (note is not None and note != s.note))
        s.kind, s.capacity = new_kind, new_cap
        if location is not None:
            s.location = location[:200]
        if note is not None:
            s.note = note[:500]
        if changed_info:
            for b in repo.active_bookings_for_slot(db, s.id):
                ev = repo.add_event(db, b.id, actor.id, "slot_changed")
                enqueue(db, b, ev, "slot_changed")
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
            ev = repo.add_event(db, b.id, actor.id, "cancel_by_slot", reason)
            enqueue(db, b, ev, "cancelled")
        s.status = "cancelled"
        s.booked_count = 0
        audit_repo.add(db, actor.id, "slot.cancel", "slot", s.id,
                       {"cancelled_bookings": len(active), "reason": reason[:200]})
        return {"cancelled_bookings": len(active)}

    return _atomic(db, work)


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


def _check_slot_for(db: Session, actor: User, slot: Slot | None, now: datetime, pol: Policy,
                    *, rescheduling: bool = False) -> Slot:
    if slot is None or slot.status != "open":
        raise NotFound("예약 가능한 상담 시간이 아닙니다")
    if _is_staff(actor):
        if slot.start_at <= now:
            raise Conflict("이미 지난 상담 시간입니다", code="slot_past")
    else:
        policy_mod.check_student_booking_time(slot.start_at, now, pol, enforce_window=not rescheduling)
    return slot


def book(db: Session, actor: User, slot_id: int, student_id: int | None = None,
         topic: str = "", now: datetime | None = None, *,
         applicant_name: str = "", student_number: str = "", grade: int | None = None,
         consultation_type: str = "other", consultation_mode: str = "in_person") -> Booking:
    pol = _policy(db)
    student = _resolve_student(db, actor, student_id)

    def work():
        # Serialize against staff time edits before validating the latest slot.
        # populate_existing prevents an earlier identity-map read from staying stale.
        locked = db.scalar(select(Slot).where(Slot.id == slot_id).with_for_update()
                           .execution_options(populate_existing=True))
        slot = _check_slot_for(db, actor, locked, now or utcnow(), pol)
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
        ev = repo.add_event(db, b.id, actor.id, "book" if actor.id == student.id else "book_by_staff")
        enqueue(db, b, ev, "created")
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
        ev = repo.add_event(db, b.id, actor.id, "cancel_by_staff" if staff else "cancel", reason)
        enqueue(db, b, ev, "cancelled")
        if staff:
            audit_repo.add(db, actor.id, "booking.cancel_by_staff", "booking", b.id,
                           {"student_id": b.student_id, "reason": reason[:200]})
        return b

    b = _atomic(db, work)
    db.refresh(b)
    return b


def reschedule(db: Session, actor: User, booking_id: int, new_slot_id: int, reason: str = "",
               now: datetime | None = None, *, expected_slot_id: int | None = None) -> Booking:
    """Move the existing booking atomically, preserving identity and all history."""
    pol = _policy(db)
    staff = _is_staff(actor)

    def work():
        booking = _visible_booking(db, actor, booking_id, lock=True)
        # A concurrent move may have committed while this request waited for
        # the booking lock. Refresh before checking its current slot/status.
        db.refresh(booking)
        if booking.status != "booked":
            raise Conflict("진행 중인 예약만 변경할 수 있습니다")
        if expected_slot_id is not None and booking.slot_id != expected_slot_id:
            raise Conflict("예약 시간이 이미 변경되었습니다. 새로고침 후 다시 선택해 주세요",
                           code="booking_changed")
        if booking.slot_id == new_slot_id:
            raise BadRequest("같은 상담 시간입니다")
        # Serialize seat transfers in a consistent slot order, including moves
        # in opposite directions. Capacity updates remain conditional in SQL.
        locked = {slot.id: slot for slot in db.scalars(select(Slot)
                  .where(Slot.id.in_([booking.slot_id, new_slot_id])).order_by(Slot.id)
                  .with_for_update().execution_options(populate_existing=True))}
        previous = locked[booking.slot_id]
        if previous.status != "open":
            raise Conflict("기존 상담 시간이 취소되었습니다. 새로고침해 주세요")
        checked_at = now or utcnow()  # Recheck the deadline after lock waits.
        if not staff:
            policy_mod.check_student_cancel_time(previous.start_at, checked_at, pol)
        target = _check_slot_for(db, actor, locked.get(new_slot_id), checked_at, pol, rescheduling=True)
        if not repo.try_take_seat(db, target.id):
            raise Conflict("변경하려는 시간의 정원이 마감되었습니다. 기존 예약은 유지됩니다", code="slot_full")
        old_slot_id = previous.id
        old = SimpleNamespace(id=booking.id,
                              slot=SimpleNamespace(start_at=previous.start_at, end_at=previous.end_at))
        repo.release_seat(db, old_slot_id)
        booking.slot_id = target.id
        booking.slot = target  # Keep the response and notification relationship fresh.
        db.flush()
        detail = (f"slot {old_slot_id} [{previous.start_at.isoformat()}~{previous.end_at.isoformat()}] "
                  f"{previous.kind} {previous.location[:60]} → "
                  f"slot {target.id} [{target.start_at.isoformat()}~{target.end_at.isoformat()}] "
                  f"{target.kind} {target.location[:60]}")
        if reason.strip():
            detail += f"; {reason.strip()}"
        ev = repo.add_event(db, booking.id, actor.id, "rescheduled", detail)
        # Keep the original slot protected as historical even though the
        # booking row now points at its new slot (no schema/backfill required).
        audit_repo.add(db, actor.id, "slot.booking_moved", "slot", old_slot_id,
                       {"booking_id": booking.id, "to_slot": target.id})
        enqueue(db, booking, ev, "changed", old=old)
        if staff:
            audit_repo.add(db, actor.id, "booking.reschedule_by_staff", "booking", booking.id,
                           {"from_slot": old_slot_id, "to_slot": target.id,
                            "student_id": booking.student_id, "reason": reason[:200]})
        return booking

    booking = _atomic(db, work)
    db.refresh(booking)
    return booking


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


def delete_empty_cancelled_slot(db: Session, actor: User, slot_id: int) -> None:
    if not _is_staff(actor):
        raise Forbidden("상담 시간 관리 권한이 없습니다")

    def work():
        slot = repo.get_slot(db, slot_id, lock=True)
        if slot is None:
            raise NotFound("상담 시간을 찾을 수 없습니다")
        if actor.role != "admin" and slot.created_by_id != actor.id:
            raise Forbidden("본인이 등록한 상담 시간만 삭제할 수 있습니다")
        if slot.status != "cancelled" or slot.booked_count or repo.booked_slot_ids(db, [slot_id]):
            raise Conflict("취소 상태이며 예약 이력이 전혀 없는 상담 시간만 삭제할 수 있습니다")
        audit_repo.add(db, actor.id, "slot.delete_empty_cancelled", "slot", slot.id,
                       {"start_at": slot.start_at.isoformat(), "end_at": slot.end_at.isoformat()})
        db.delete(slot)

    _atomic(db, work)


def available_days(db: Session, viewer: User, now: datetime | None = None) -> list[dict]:
    """Available dates without an artificial rescheduling horizon or N queries."""
    from sqlalchemy import select

    now = now or utcnow()
    pol = _policy(db)
    active = None if _is_staff(viewer) else repo.active_booking_of(db, viewer.id)
    query = select(Slot.start_at).where(
        Slot.status == "open", Slot.booked_count < Slot.capacity, Slot.start_at > now,
        Slot.start_at >= now + timedelta(minutes=pol.booking_deadline_minutes))
    if active is None:
        query = query.where(Slot.start_at <= now + timedelta(days=pol.booking_window_days))
    else:
        query = query.where(Slot.id != active.slot_id)
    counts: dict[str, int] = {}
    for start_at in db.scalars(query):
        day = start_at.astimezone(KST).date().isoformat()
        counts[day] = counts.get(day, 0) + 1
    return [{"date": day, "count": count} for day, count in sorted(counts.items())]
