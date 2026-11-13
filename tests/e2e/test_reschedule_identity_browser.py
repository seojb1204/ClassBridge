"""Real-browser edit uses one request, one booking ID, no cancel/rebook steps."""
import json
import os
from datetime import timedelta

import pytest

from app.db import utcnow
from app.timeutil import today_kst
from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_one_click_same_id_change_beyond_new_booking_horizon(server, browser, viewport):  # noqa: F811
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    student = Session(browser, base, f"edit-{viewport['width']}@example.test", viewport, service_workers="block")
    def post(session, path, payload):
        csrf = session.ctx.request.get(base + "/api/me").json()["csrf_token"]
        response = session.ctx.request.post(base + path, data=json.dumps(payload),
                                           headers={"X-CSRF-Token": csrf, "Content-Type": "application/json"})
        assert response.ok, response.text()
        return response.json()
    near_day = today_kst(utcnow()) + timedelta(days=2 + (viewport == MOBILE))
    far_day = near_day + timedelta(days=60)
    slots = []
    for day in (near_day, far_day):
        slots.append(post(prof, "/api/slots", {"start_date": day.isoformat(), "start_time": "10:00",
                     "end_time": "10:30", "duration_minutes": 30})["slot_ids"][0])
    original = post(student, "/api/bookings", {"slot_id": slots[0], "topic": "synthetic retained topic"})
    requests = []
    student.page.on("request", lambda request: requests.append(request.url)
                    if request.method == "POST" and "/api/bookings" in request.url else None)
    student.go("/booking")
    panel = student.page.locator(".available-days")
    if panel.get_by_role("button", name="전체 일정 보기", exact=True).count():
        panel.get_by_role("button", name="전체 일정 보기", exact=True).click()
    panel.get_by_role("button", name=f"{far_day.month}월 {far_day.day}일", exact=False).click()
    student.page.locator(f'.slot.open[data-slot-id="{slots[1]}"]').click()
    modal = student.page.locator(".modal")
    modal.get_by_text("변경 전:", exact=False).wait_for()
    modal.get_by_text("변경 후:", exact=False).wait_for()
    assert modal.get_by_text("취소", exact=False).count() > 0
    modal.get_by_role("button", name="이 시간으로 변경", exact=True).click()
    student.toast("예약이 변경되었습니다.")
    assert requests == [f"{base}/api/bookings/{original['id']}/reschedule"]
    student.go("/my-bookings")
    assert student.page.locator(".card.booking").count() == 1
    assert student.page.locator(f".card.booking.booked[data-booking-id='{original['id']}']").count() == 1
    assert student.page.get_by_text("synthetic retained topic", exact=True).count() == 1
    data = student.ctx.request.get(base + "/api/bookings/mine").json()
    assert len(data) == 1 and data[0]["id"] == original["id"] and data[0]["slot"]["id"] == slots[1]
    student.close()
    prof.close()
