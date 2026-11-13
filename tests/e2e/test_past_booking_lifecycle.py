"""Disposable-browser reproduction of historical booking blockage and recovery.

No live services, accounts, or messages: uses the existing isolated SQLite server
fixture with notification channels disabled by default.
"""
import json
import os
import time
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session as DbSession

from app.db import make_engine, utcnow
from app.models import AppSetting, Booking, BookingEvent, Notification, Slot, User
from tests.e2e.test_e2e import MOBILE, PC, Session, _find_slot, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [PC, MOBILE])
@pytest.mark.parametrize("scenario", ["historical", "recent", "ongoing"])
def test_past_booking_worker_then_new_booking(server, browser, viewport, scenario):  # noqa: F811
    base, db_path = server
    staff = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    email = f"lifecycle-{scenario}-{viewport['width']}@example.test"
    student = Session(browser, base, email, viewport, service_workers="block")
    engine = make_engine(f"sqlite:///{db_path}")
    # Let the real worker finish login-triggered empty scans before seeding the
    # deliberately inconsistent old record. Foreground GETs do not wake it.
    time.sleep(0.5)
    now = utcnow()
    since = now - timedelta(days=2)
    old_start = now - timedelta(days=7) if scenario == "historical" else now - timedelta(minutes=20)
    old_end = old_start + timedelta(minutes=30 if scenario == "ongoing" else 10)
    with DbSession(engine) as db, db.begin():
        teacher = db.query(User).filter_by(email="prof@test.ac.kr").one()
        user = db.query(User).filter_by(email=email).one()
        marker = db.get(AppSetting, "booking_auto_complete_since")
        marker.value = since.isoformat()
        old_slot = Slot(start_at=old_start, end_at=old_end, created_by_id=teacher.id, booked_count=1)
        # Stagger each fixture so students have an unambiguous available target.
        hour_offset = ["historical", "recent", "ongoing"].index(scenario) * 2 + (viewport == MOBILE)
        future = now + timedelta(days=5, hours=hour_offset)
        new_slot = Slot(start_at=future, end_at=future + timedelta(minutes=30), created_by_id=teacher.id)
        db.add_all([old_slot, new_slot])
        db.flush()
        booking = Booking(slot_id=old_slot.id, student_id=user.id, created_by_id=user.id,
                          applicant_name="Lifecycle fixture", professor_note="synthetic preserved note")
        db.add(booking)
        db.flush()
        db.add(BookingEvent(booking_id=booking.id, actor_id=user.id, action="book", detail="synthetic history"))
        old_id, new_slot_id, user_id = booking.id, new_slot.id, user.id
    student.go("/booking")
    _find_slot(student).click()
    student.page.get_by_role("heading", name="예약 변경", exact=True).wait_for()
    student.page.get_by_text("기존 예약(", exact=False).wait_for()
    student.page.get_by_role("button", name="닫기", exact=True).click()
    # Authenticated synthetic staff write triggers the production wake path.
    csrf = staff.ctx.request.get(base + "/api/me").json()["csrf_token"]
    response = staff.ctx.request.patch(base + f"/api/slots/{new_slot_id}",
                                      data=json.dumps({"note": "synthetic wake"}),
                                      headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"})
    assert response.status == 200, response.text()
    expected = {"historical": "expired", "recent": "completed", "ongoing": "booked"}[scenario]
    for _ in range(50):
        with DbSession(engine) as db:
            status = db.get(Booking, old_id).status
        if status == expected:
            break
        time.sleep(0.1)
    assert status == expected
    student.go("/booking")
    _find_slot(student).click()
    if scenario == "ongoing":
        student.page.get_by_role("button", name="이 시간으로 변경", exact=True).click()
        student.toast("상담 시작 30분 전까지만 취소·변경할 수 있습니다")
        student.page.get_by_role("button", name="닫기", exact=True).click()
        with DbSession(engine) as db:
            assert db.query(Booking).filter_by(student_id=user_id).count() == 1
            assert db.get(Booking, old_id).status == "booked"
    else:
        student.page.get_by_role("heading", name="상담 예약", exact=True).wait_for()
        assert student.page.get_by_text("기존 예약(", exact=False).count() == 0
        student.page.get_by_role("button", name="예약하기", exact=True).click()
        student.toast("예약이 완료되었습니다.")
        student.go("/my-bookings")
        assert student.page.locator(f".card.booking.{expected}").count() == 1
        assert student.page.locator(".card.booking.booked").count() == 1
        assert "synthetic preserved note" not in student.page.locator("body").inner_text()
        with DbSession(engine) as db:
            assert db.query(Booking).filter_by(student_id=user_id).count() == 2
            assert db.get(Booking, old_id).professor_note == "synthetic preserved note"
            assert db.query(BookingEvent).filter_by(booking_id=old_id).count() == 1
            assert db.query(Notification).count() == 0
    student.close()
    staff.close()
    engine.dispose()
