"""Staff-only names, expanded notices, and bounded week prefetch (synthetic data)."""
import os
from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import expect

from app.db import utcnow
from app.timeutil import today_kst
from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E not set")


@pytest.mark.parametrize("viewport", [PC, MOBILE, {"width": 360, "height": 760}])
def test_staff_calendar_names_and_cached_navigation(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    p = staff.page
    day = today_kst(utcnow())
    week = day - timedelta(days=day.weekday())
    calls = []
    names = ["<b>예약학생</b>", "완료학생", "미참석학생", "기간지난학생"]

    def rows(start):
        return [{"id": 8800 + i, "start_at": f"{start}T{10+i}:00:00+09:00",
                 "end_at": f"{start}T{10+i}:30:00+09:00", "kind": "individual", "capacity": 1,
                 "remaining": 0, "status": "open", "bookable": False, "reason": "이미 지난 시간",
                 "mine": False, "note": "", "location": ""} for i in range(4)]

    def route_api(route):
        url = urlparse(route.request.url)
        start = parse_qs(url.query).get("start", [week.isoformat()])[0]
        calls.append(url.path + "?" + url.query)
        if url.path == "/api/slots":
            value = rows(start)
        elif url.path == "/api/lectures":
            value = []
        else:
            statuses = ["booked", "completed", "no_show", "expired"]
            value = [{"id": 9900+i, "slot": slot, "status": status,
                      "applicant_name": names[i], "student_name": "원래 이름", "professor_note": ""}
                     for i, (slot, status) in enumerate(zip(rows(start), statuses, strict=True))]
            value.append({**value[0], "id": 9999, "applicant_name": "취소학생", "status": "cancelled"})
        route.fulfill(json=value)

    for resource in ["slots", "bookings", "lectures"]:
        p.route(f"**/api/{resource}?*", route_api)
    # Reload after installing routes; the staff landing page is already /slots.
    p.reload()
    staff.go("/slots")
    expect(p.locator('[data-slot-id="8800"]')).to_contain_text(names[0])
    for i, name in enumerate(names):
        expect(p.locator(f'[data-slot-id="{8800+i}"]')).to_contain_text(name)
    assert p.locator('[data-slot-id="8800"] b').count() == 0
    assert p.locator(".week-grid").get_by_text("취소학생", exact=False).count() == 0
    assert p.get_by_role("button", name="+ 강의 추가", exact=True).count() == 0
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # Allow adjacent-week background GETs to finish, then navigation reuses them.
    p.wait_for_load_state("networkidle")
    next_week = (week + timedelta(days=7)).isoformat()
    expected = f"/api/bookings?start={next_week}&days=7"
    assert calls.count(expected) == 1
    p.get_by_role("button", name="다음 주", exact=True).click()
    expect(p.locator('.week-nav')).to_contain_text(str((week + timedelta(days=7)).day))
    p.wait_for_load_state("networkidle")
    assert calls.count(expected) == 1
    # Explicit refresh invalidates cached private data.
    staff.go("/bookings")
    staff.go("/slots")
    p.wait_for_load_state("networkidle")
    assert calls.count(expected) == 2
    staff.shot("staff_calendar_names_" + str(viewport["width"]))
    staff.close()
