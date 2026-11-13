"""상담 예약 정책·예외 처리 (지시서 §3.3, §3.4)."""
from __future__ import annotations

from datetime import timedelta

from app.db import utcnow
from app.models import Blackout, Slot
from app.timeutil import today_kst
from tests.conftest import future_day, make_slots


def _slot_state(app, sid):
    db = app.state.SessionLocal()
    try:
        s = db.get(Slot, sid)
        return s.booked_count, s.capacity, s.status
    finally:
        db.close()


def test_student_flow_book_view_cancel(app, clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    slots = s1.get(f"/api/slots?start={future_day().isoformat()}&days=1").json()
    assert [x["id"] for x in slots] == ids and all(x["bookable"] for x in slots)
    r = s1.post("/api/bookings", json={"slot_id": ids[0], "topic": "진로 상담"})
    assert r.status_code == 201
    bid = r.json()["id"]
    assert _slot_state(app, ids[0])[0] == 1
    slots = s1.get(f"/api/slots?start={future_day().isoformat()}&days=1").json()
    assert slots[0]["mine"] and not slots[0]["bookable"] and slots[0]["remaining"] == 0
    assert s1.post(f"/api/bookings/{bid}/cancel", json={}).json()["status"] == "cancelled"
    assert _slot_state(app, ids[0])[0] == 0


def test_one_active_booking_per_student(clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    assert s1.post("/api/bookings", json={"slot_id": ids[0]}).status_code == 201
    r = s1.post("/api/bookings", json={"slot_id": ids[1]})
    assert r.status_code == 409 and r.json()["error"] == "active_booking_exists"


def test_duplicate_click_same_slot(clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    codes = [s1.post("/api/bookings", json={"slot_id": ids[0]}).status_code for _ in range(3)]
    assert codes == [201, 409, 409]


def test_individual_slot_capacity_and_group_remaining(app, clients):
    p, s1, s2, s3 = clients["prof"], clients["s1"], clients["s2"], clients["s3"]
    ind = make_slots(p, start="09:00", end="09:30")
    assert s1.post("/api/bookings", json={"slot_id": ind[0]}).status_code == 201
    r = s2.post("/api/bookings", json={"slot_id": ind[0]})
    assert r.status_code == 409 and r.json()["error"] == "slot_full"
    grp = make_slots(p, start="14:00", end="15:00", duration=60, kind="group", capacity=2)
    assert s2.post("/api/bookings", json={"slot_id": grp[0]}).status_code == 201
    view = s3.get(f"/api/slots?start={future_day().isoformat()}&days=1").json()
    g = next(x for x in view if x["id"] == grp[0])
    assert g["remaining"] == 1 and g["kind"] == "group"
    assert s3.post("/api/bookings", json={"slot_id": grp[0]}).status_code == 201
    assert _slot_state(app, grp[0])[:2] == (2, 2)


def test_individual_requires_capacity_one(clients):
    p = clients["prof"]
    r = p.post("/api/slots", json={"start_date": future_day().isoformat(), "start_time": "10:00",
                                   "end_time": "11:00", "duration_minutes": 30, "kind": "individual", "capacity": 3})
    assert r.status_code == 400


def test_cancel_deadline_thirty_minutes(app, clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    # 상담 시작을 29분 뒤로 옮겨 마감 상황 재현 (테스트 DB)
    db = app.state.SessionLocal()
    s = db.get(Slot, ids[0])
    s.start_at = utcnow() + timedelta(minutes=29)
    s.end_at = s.start_at + timedelta(minutes=30)
    db.commit()
    db.close()
    r = s1.post(f"/api/bookings/{bid}/cancel", json={})
    assert r.status_code == 409 and r.json()["error"] == "cancel_deadline"
    # 교수자는 사유와 함께 취소 가능
    assert p.post(f"/api/bookings/{bid}/cancel", json={}).status_code == 400
    assert p.post(f"/api/bookings/{bid}/cancel", json={"reason": "교수 일정"}).status_code == 200


def test_booking_deadline_and_window(app, clients):
    p, s1, a = clients["prof"], clients["s1"], clients["admin"]
    today = today_kst(utcnow())
    far = make_slots(p, day=today + timedelta(days=40))
    r = s1.post("/api/bookings", json={"slot_id": far[0]})
    assert r.status_code == 409 and r.json()["error"] == "booking_window"
    a.put("/api/admin/settings", json={"booking_window_days": 60})
    assert s1.post("/api/bookings", json={"slot_id": far[0]}).status_code == 201


def test_half_hour_availability_matches_booking_and_date_filter(app, clients, monkeypatch):
    prof, student = clients["prof"], clients["s1"]
    day = future_day()
    first, second = make_slots(prof, day=day)
    with app.state.SessionLocal() as db:
        start = db.get(Slot, first).start_at
    monkeypatch.setattr("app.services.booking_service.utcnow", lambda: start - timedelta(seconds=1))
    slots = student.get(f"/api/slots?start={day}&days=1").json()
    assert [(s["id"], s["bookable"]) for s in slots] == [(first, False), (second, True)]
    assert student.post("/api/bookings", json={"slot_id": first}).json()["error"] == "booking_deadline"
    bid = student.post("/api/bookings", json={"slot_id": second}).json()["id"]
    assert [b["id"] for b in prof.get(f"/api/bookings?from_date={day}").json()] == [bid]
    assert prof.get(f"/api/bookings?from_date={day + timedelta(days=1)}").json() == []


def test_reschedule_success_and_atomic_failure(app, clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    ids = make_slots(p)  # 10:00, 10:30
    full = make_slots(p, start="13:00", end="13:30")
    assert s2.post("/api/bookings", json={"slot_id": full[0]}).status_code == 201
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    # 마감된 시간으로 변경 시도 → 실패, 기존 예약 유지
    r = s1.post(f"/api/bookings/{bid}/reschedule", json={"new_slot_id": full[0]})
    assert r.status_code == 409
    mine = [b for b in s1.get("/api/bookings/mine").json() if b["status"] == "booked"]
    assert len(mine) == 1 and mine[0]["id"] == bid
    assert _slot_state(app, ids[0])[0] == 1 and _slot_state(app, full[0])[0] == 1
    # 정상 변경
    r = s1.post(f"/api/bookings/{bid}/reschedule", json={"new_slot_id": ids[1]})
    assert r.status_code == 200
    assert _slot_state(app, ids[0])[0] == 0 and _slot_state(app, ids[1])[0] == 1
    hist = p.get(f"/api/bookings/{r.json()['id']}/history").json()
    assert hist[0]["action"] == "rescheduled_to"


def test_cancel_then_other_student_books(clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    ids = make_slots(p, start="10:00", end="10:30")
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    s1.post(f"/api/bookings/{bid}/cancel", json={})
    assert s2.post("/api/bookings", json={"slot_id": ids[0]}).status_code == 201


def test_capacity_cannot_drop_below_booked(clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    grp = make_slots(p, start="14:00", end="15:00", duration=60, kind="group", capacity=3)
    s1.post("/api/bookings", json={"slot_id": grp[0]})
    s2.post("/api/bookings", json={"slot_id": grp[0]})
    r = p.patch(f"/api/slots/{grp[0]}", json={"capacity": 1})
    assert r.status_code == 409 and r.json()["error"] == "capacity_below_booked"
    assert p.patch(f"/api/slots/{grp[0]}", json={"capacity": 2}).status_code == 200


def test_delete_slot_with_bookings_requires_force(app, clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    r = p.post(f"/api/slots/{ids[0]}/cancel", json={})
    assert r.status_code == 409 and r.json()["error"] == "slot_has_bookings"
    assert p.post(f"/api/slots/{ids[0]}/cancel", json={"force": True}).status_code == 400  # 사유 필수
    r = p.post(f"/api/slots/{ids[0]}/cancel", json={"force": True, "reason": "출장"})
    assert r.json() == {"cancelled_bookings": 1}
    b = next(x for x in s1.get("/api/bookings/mine").json() if x["id"] == bid)
    assert b["status"] == "cancelled" and "출장" in b["cancel_reason"]
    # 학생 화면에서 취소된 시간은 보이지 않음
    view = s1.get(f"/api/slots?start={future_day().isoformat()}&days=1").json()
    assert ids[0] not in [x["id"] for x in view]


def test_slot_overlap_rejected(clients):
    p = clients["prof"]
    make_slots(p, start="10:00", end="11:00")
    r = p.post("/api/slots", json={"start_date": future_day().isoformat(), "start_time": "10:45",
                                   "end_time": "11:30", "duration_minutes": 30})
    assert r.status_code == 409 and r.json()["error"] == "slot_overlap"


def test_break_and_repeat_generation(clients):
    p = clients["prof"]
    day = future_day(3)
    ids = make_slots(p, day=day, start="10:00", end="11:00", duration=20, break_minutes=10, repeat_weeks=2)
    # 10:00-10:20, 10:30-10:50 × 2주
    assert len(ids) == 4


def test_only_registered_slots_control_availability(app, clients):
    p, student = clients["prof"], clients["s1"]
    day = future_day(9)
    # Retained legacy storage must no longer silently block availability.
    with app.state.SessionLocal() as db:
        db.add(Blackout(day=day, reason="legacy", created_by_id=p.me["id"]))
        db.commit()
    spec = {"start_date": day.isoformat(), "start_time": "10:00", "end_time": "11:00",
            "duration_minutes": 30, "repeat_weeks": 2}
    preview = p.post("/api/slots/preview", json=spec)
    assert preview.status_code == 200
    assert preview.json()["created"] == 4 and preview.json()["skipped_blackout_days"] == []
    created = p.post("/api/slots", json=spec)
    assert created.status_code == 201 and created.json()["created"] == 4
    ids = created.json()["slot_ids"]
    slots = student.get(f"/api/slots?start={day}&days=7").json()
    assert len(slots) == 2 and all(s["bookable"] for s in slots)
    assert student.post("/api/bookings", json={"slot_id": 999999}).status_code == 404
    p.post(f"/api/slots/{ids[0]}/cancel", json={})
    assert student.post("/api/bookings", json={"slot_id": ids[0]}).status_code == 404
    assert student.post("/api/bookings", json={"slot_id": ids[1]}).status_code == 201
    assert student.get(f"/api/slots?start={future_day(8)}&days=1").json() == []
    with app.state.SessionLocal() as db:
        assert db.query(Blackout).count() == 1  # no destructive migration or cleanup


def test_retired_blackout_routes_do_not_create_or_remove_data(app, clients):
    for client in clients.values():
        assert client.get("/api/blackouts").status_code == 404
        assert client.post("/api/blackouts", json={"day": future_day().isoformat()}).status_code == 404
        assert client.delete("/api/blackouts/1").status_code == 404
    with app.state.SessionLocal() as db:
        assert db.query(Blackout).count() == 0


def test_outcome_requires_slot_started(app, clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    assert p.post(f"/api/bookings/{bid}/outcome", json={"outcome": "completed"}).status_code == 409
    db = app.state.SessionLocal()
    s = db.get(Slot, ids[0])
    s.start_at = utcnow() - timedelta(minutes=40)
    s.end_at = utcnow() - timedelta(minutes=10)
    db.commit()
    db.close()
    r = p.post(f"/api/bookings/{bid}/outcome", json={"outcome": "completed"})
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert p.post(f"/api/bookings/{bid}/outcome", json={"outcome": "no_show"}).json()["status"] == "no_show"
    # 완료 후에는 학생이 새 예약 가능 (활성 예약 아님)
    new = make_slots(p, start="16:00", end="16:30")
    assert s1.post("/api/bookings", json={"slot_id": new[0]}).status_code == 201


def test_staff_books_on_behalf_and_audit(clients):
    p, s1, a = clients["prof"], clients["s1"], clients["admin"]
    ids = make_slots(p)
    r = p.post("/api/bookings", json={"slot_id": ids[0], "student_id": s1.me["id"]})
    assert r.status_code == 201 and r.json()["student_email"] == "s1@test.ac.kr"
    assert p.post("/api/bookings", json={"slot_id": ids[1], "student_id": p.me["id"]}).status_code == 403
    logs = a.get("/api/admin/audit?action=booking.create_for_student").json()
    assert len(logs) == 1


def test_professor_cannot_self_book(clients):
    p = clients["prof"]
    ids = make_slots(p)
    assert p.post("/api/bookings", json={"slot_id": ids[0]}).status_code == 403


def test_db_unavailable_returns_503(app, clients):
    from sqlalchemy.exc import OperationalError

    def boom():
        raise OperationalError("SELECT 1", {}, Exception("down"))

    app.state.SessionLocal_backup = app.state.SessionLocal

    class Broken:
        def __call__(self):
            s = app.state.SessionLocal_backup()
            s.execute = lambda *a, **k: boom()
            return s

    app.state.SessionLocal = Broken()
    r = clients["s1"].get("/api/me")
    assert r.status_code == 503 and r.json()["error"] == "db_unavailable"
    app.state.SessionLocal = app.state.SessionLocal_backup


def test_staff_unbounded_bookings_include_distant_dates_and_filter_status(app, clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    ids = make_slots(p)
    first = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    second = s2.post("/api/bookings", json={"slot_id": ids[1]}).json()["id"]
    assert s2.post(f"/api/bookings/{second}/cancel", json={}).status_code == 200
    with app.state.SessionLocal() as db:
        slot = db.get(Slot, ids[0])
        slot.start_at += timedelta(days=90)
        slot.end_at += timedelta(days=90)
        db.commit()
    for staff in (p, clients["admin"]):
        response = staff.get("/api/bookings?status=booked")
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [first]
        assert {row["id"] for row in staff.get("/api/bookings").json()} == {first, second}
    assert s1.get("/api/bookings?status=booked").status_code == 403


def test_staff_can_move_student_without_reason(clients):
    professor, student = clients["prof"], clients["s1"]
    first, second = make_slots(professor)
    original = student.post("/api/bookings", json={"slot_id": first}).json()["id"]
    result = professor.post(f"/api/bookings/{original}/reschedule", json={"new_slot_id": second})
    assert result.status_code == 200
    moved = result.json()
    assert moved["slot"]["id"] == second and moved["student_id"] == student.me["id"]
    history = professor.get(f"/api/bookings/{moved['id']}/history").json()
    assert history[0]["action"] == "rescheduled_to"
