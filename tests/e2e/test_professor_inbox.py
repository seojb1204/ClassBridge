"""Professor's durable inbox works without browser push registration."""
import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_professor_inbox_read_and_refresh(server, browser, viewport):  # noqa: F811
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    calls = []
    item = {"id": 1, "kind": "created", "title": "새 상담 예약", "body": "예약 관리에서 확인하세요.",
            "url": "#/bookings", "created_on": "2026-11-13", "read": False}
    def inbox(route):
        calls.append(route.request.method)
        if route.request.method == "PUT":
            item["read"] = True
            route.fulfill(json={"ok": True})
        else:
            route.fulfill(json={"items": [item], "unread": int(not item["read"])})
    prof.page.route("**/api/inbox**", inbox)
    prof.go("/inbox")
    prof.page.get_by_role("heading", name="내 알림", exact=True).wait_for()
    prof.page.get_by_text("읽지 않은 알림 1건", exact=True).wait_for()
    prof.page.get_by_role("button", name="읽음 표시", exact=True).click()
    prof.page.get_by_text("읽지 않은 알림 0건", exact=True).wait_for()
    assert calls.count("PUT") == 1
    assert prof.page.locator("body").evaluate("e => e.scrollWidth <= innerWidth")
    prof.page.get_by_role("button", name="알림 새로고침").click()
    assert prof.page.get_by_role("button", name="읽음", exact=True).is_disabled()
    prof.ctx.close()
