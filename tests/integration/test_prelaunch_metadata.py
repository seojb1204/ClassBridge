"""Regression tests for pre-launch booking and survey application fields."""
from __future__ import annotations

from tests.conftest import make_slots


def test_booking_metadata_roundtrip_and_reschedule(clients):
    prof, student = clients["prof"], clients["s1"]
    slots = make_slots(prof)
    booking = student.post("/api/bookings", json={
        "slot_id": slots[0], "topic": "진로 선택",
        "applicant_name": "홍길동", "student_number": "20260001", "grade": 2,
        "consultation_type": "career", "consultation_mode": "online",
    })
    assert booking.status_code == 201, booking.text
    body = booking.json()
    assert body["applicant_name"] == "홍길동"
    assert body["student_number"] == "20260001"
    assert body["grade"] == 2
    assert body["consultation_type"] == "career"
    assert body["consultation_mode"] == "online"
    moved = student.post(f"/api/bookings/{body['id']}/reschedule", json={"new_slot_id": slots[1]})
    assert moved.status_code == 200, moved.text
    for field in ("applicant_name", "student_number", "grade", "consultation_type", "consultation_mode"):
        assert moved.json()[field] == body[field]
    visible = prof.get("/api/bookings").json()
    assert any(x["id"] == moved.json()["id"] and x["student_number"] == "20260001" for x in visible)


def test_old_booking_payload_remains_compatible(clients):
    prof, student = clients["prof"], clients["s1"]
    slot = make_slots(prof)[0]
    r = student.post("/api/bookings", json={"slot_id": slot})
    assert r.status_code == 201, r.text
    assert r.json()["consultation_type"] == "other"
    assert r.json()["consultation_mode"] == "in_person"


def test_survey_course_semester_create_edit_clone(clients):
    prof, student = clients["prof"], clients["s1"]
    r = prof.post("/api/surveys", json={
        "title": "강의 점검", "course_name": "항공서비스 실무", "semester": "2026-2",
        "questions": [{"qtype": "scale5", "title": "수업 이해도", "required": True}],
    })
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["course_name"] == "항공서비스 실무"
    assert prof.patch(f"/api/surveys/{sid}", json={"semester": "2026년 2학기"}).status_code == 200
    assert prof.post(f"/api/surveys/{sid}/publish").status_code == 200
    assert student.get("/api/surveys/student/list").json()[0]["course_name"] == "항공서비스 실무"
    assert prof.patch(f"/api/surveys/{sid}", json={"course_name": "다른 과목"}).status_code == 409
    clone = prof.post(f"/api/surveys/{sid}/duplicate")
    assert clone.status_code == 201, clone.text
    assert clone.json()["semester"] == "2026년 2학기"
