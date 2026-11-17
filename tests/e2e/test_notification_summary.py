"""Compact notification rows and read-first booking summary, real Chromium viewports."""
import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [MOBILE, PC])
def test_compact_rows_summary_manage_and_back(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    p = staff.page
    try:
        slot = {"id": 99881, "start_at": "2026-11-19T05:00:00Z", "end_at": "2026-11-19T05:30:00Z",
                "capacity": 1, "kind": "individual", "status": "open", "remaining": 0, "bookable": False}
        booking = {"id": 99882, "slot": slot, "status": "booked", "student_name": "요약 테스트",
                   "student_email": "private@example.test", "grade": 1, "topic": "상담 질문",
                   "professor_note": "보존할 기록"}
        item = {"id": 99883, "kind": "created", "title": "새 상담 예약", "read": False,
                "body": "현재 예약 · 11/19(목) 14:00–14:30 · 예약됨", "url": "/#/inbox/99883",
                "arrived_at": "2026-11-17T18:19:00+09:00", "booking_summary": {"student_name": "요약 테스트"}}
        writes = []

        def inbox(route):
            if route.request.url.endswith('/target'):
                route.fulfill(json={"type": "booking", "booking": booking, "notification": item})
            elif route.request.method == "PUT":
                item["read"] = True
                writes.append(route.request.url)
                route.fulfill(json={"ok": True, "unread": 0})
            else:
                route.fulfill(json={"items": [item], "unread": int(not item["read"])})

        p.route("**/api/inbox**", inbox)
        p.route("**/api/slots?*", lambda r: r.fulfill(json=[slot]))
        p.route("**/api/bookings?*", lambda r: r.fulfill(json=[booking]))
        p.route("**/api/lectures?*", lambda r: r.fulfill(json=[{**slot, "event_type": "lecture",
            "title": "같은 번호 강의", "start_at": "2026-11-19T04:00:00Z", "end_at": "2026-11-19T04:30:00Z"}]))
        staff.go('/inbox')
        row = p.locator('.inbox-row-link').first
        row.get_by_role('heading', name='새 상담 예약 · 요약 테스트').wait_for()
        assert row.locator('.sr-only').evaluate('e => e.getBoundingClientRect().width') <= 1
        assert row.locator('.sr-only').evaluate('e => getComputedStyle(e).position') == 'absolute'
        assert 'private@example.test' not in row.inner_text()
        assert row.bounding_box()['height'] >= 44
        row.click()
        summary = p.get_by_role('dialog', name='새 상담 예약', exact=True)
        summary.wait_for()
        p.locator(".modal:focus-within").wait_for()
        assert summary.locator('textarea,input').count() == 0
        assert summary.get_by_text('예약됨', exact=True).count() == 1
        assert summary.get_by_role('button', name='예약 취소', exact=True).count() == 0
        assert p.locator('[data-slot-id="99881"][data-event-type="consultation"].notification-target').count() >= 1
        assert p.locator('[data-event-type="lecture"].notification-target').count() == 0
        staff.shot('notification_summary_' + str(viewport['width']))
        summary.get_by_role('button', name='기록·예약 관리').click()
        editor = p.get_by_role('dialog', name='예약·상담 상세')
        editor.wait_for()
        assert editor.locator('textarea').input_value() == '보존할 기록'
        assert 'booked' not in editor.inner_text()
        assert editor.get_by_role('button', name='예약 취소', exact=True).is_visible()
        assert editor.get_by_role('button', name='기록 저장', exact=True).is_visible()
        p.keyboard.press('Escape')
        assert p.get_by_role('dialog').count() == 0
        p.go_back()
        p.wait_for_url('**/#/inbox')
        p.locator('.inbox-item.is-read').wait_for()
        assert len(writes) == 1
        assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
        staff.shot('notification_rows_' + str(viewport['width']))
    finally:
        staff.ctx.close()
