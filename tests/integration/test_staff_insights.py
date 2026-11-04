"""Professor-only consultation insights: privacy, aggregation, filters, note editing."""
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.db import utcnow
from app.models import Slot
from tests.conftest import make_slots


def test_professor_dashboard_groups_records_and_keeps_private_notes(app, clients):
    prof, admin, s1, s2 = clients["prof"], clients["admin"], clients["s1"], clients["s2"]
    first, second = make_slots(prof)
    one = s1.post("/api/bookings", json={
        "slot_id": first, "applicant_name": "학생 가", "student_number": "20260001",
        "consultation_type": "career", "consultation_mode": "online",
    })
    two = s2.post("/api/bookings", json={"slot_id": second, "consultation_type": "academics"})
    assert one.status_code == two.status_code == 201

    # The tests may adjust the disposable SQLite DB, never a live Neon database.
    db = app.state.SessionLocal()
    try:
        base = utcnow() - timedelta(days=2)
        for i, sid in enumerate((first, second)):
            slot = db.get(Slot, sid)
            slot.start_at = base + timedelta(minutes=30 * i)
            slot.end_at = slot.start_at + timedelta(minutes=30)
        db.commit()
    finally:
        db.close()

    bid1, bid2 = one.json()["id"], two.json()["id"]
    assert prof.post(f"/api/bookings/{bid1}/outcome", json={"outcome": "completed"}).status_code == 200
    assert prof.post(f"/api/bookings/{bid2}/outcome", json={"outcome": "no_show"}).status_code == 200
    assert prof.put(f"/api/bookings/{bid1}/note", json={"note": "진로 상담 비공개 메모"}).status_code == 200
    assert prof.put(f"/api/bookings/{bid2}/note", json={"note": "학업 상담 비공개 메모"}).status_code == 200

    overview = prof.get("/api/staff/overview?days=7")
    assert overview.status_code == 200, overview.text
    data = overview.json()
    assert data["total_bookings"] == 2
    assert data["status_counts"]["completed"] == 1
    assert data["status_counts"]["no_show"] == 1
    assert data["completion_rate"] == 50.0
    assert data["recorded_notes"] == 2
    assert data["type_counts"] == {"career": 1, "academics": 1}
    assert data["mode_counts"] == {"online": 1, "in_person": 1}
    assert len(data["period_start"]) == 10 and len(data["period_end"]) == 10

    listed = prof.get("/api/staff/notes?limit=1")
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert len(listed.json()["items"]) == 1
    next_page = prof.get("/api/staff/notes?limit=1&offset=1")
    assert next_page.status_code == 200
    assert listed.json()["items"][0]["booking_id"] != next_page.json()["items"][0]["booking_id"]

    by_name = admin.get("/api/staff/notes?q=%ED%95%99%EC%83%9D%20%EA%B0%80").json()
    assert by_name["total"] == 1
    assert by_name["items"][0]["note"] == "진로 상담 비공개 메모"
    assert "student_email" not in by_name["items"][0]
    by_number = prof.get("/api/staff/notes?q=20260001").json()
    assert by_number["items"][0]["booking_id"] == bid1
    by_text = prof.get("/api/staff/notes?q=%ED%95%99%EC%97%85").json()
    assert by_text["total"] == 1 and by_text["items"][0]["booking_id"] == bid2

    # Text from private consultations never enters the student API or new dashboard.
    assert "비공개 메모" not in s1.get("/api/bookings/mine").text
    assert "비공개 메모" not in overview.text


def test_dashboard_restricts_all_study_data_to_staff(app, clients):
    student = clients["s1"]
    for path in ("/api/staff/overview", "/api/staff/notes"):
        assert student.get(path).status_code == 403
        assert TestClient(app).get(path).status_code == 401
        assert clients["prof"].get(path).status_code == 200
        assert clients["admin"].get(path).status_code == 200


def test_notes_filter_requires_actual_note_and_query_is_literal(app, clients):
    prof, student = clients["prof"], clients["s1"]
    slot_id = make_slots(prof)[0]
    booking = student.post("/api/bookings", json={"slot_id": slot_id})
    assert booking.status_code == 201
    assert prof.get("/api/staff/notes").json()["total"] == 0
    assert prof.put(f"/api/bookings/{booking.json()['id']}/note",
                    json={"note": "문자 % 와 _ 포함"}).status_code == 200
    assert prof.get("/api/staff/notes?q=%25").json()["total"] == 1
    assert prof.get("/api/staff/notes?q=_").json()["total"] == 1
    assert prof.get("/api/staff/notes?q=NOT_FOUND").json()["total"] == 0


def test_staff_insights_validates_query_ranges(clients):
    prof = clients["prof"]
    for path in ("/api/staff/overview?days=0", "/api/staff/overview?days=366",
                 "/api/staff/notes?limit=0", "/api/staff/notes?limit=51",
                 "/api/staff/notes?offset=-1"):
        assert prof.get(path).status_code == 422, path
