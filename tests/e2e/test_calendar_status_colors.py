"""Calendar status colours remain distinct on desktop and both mobile views."""
import os

import pytest

from tests.e2e.test_e2e import browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("width,mode", [(1280, "week"), (390, "week"), (390, "list")])
def test_available_and_reserved_are_distinct(server, browser, width, mode):  # noqa: F811
    base, _ = server
    page = browser.new_page(viewport={"width": width, "height": 900})
    try:
        page.goto(f"{base}/static/offline.html")
        page.add_style_tag(url=f"{base}/static/css/app.css")
        page.evaluate("""async mode => {
            const {renderCalendar} = await import('/static/js/components/week-calendar.js');
            document.body.replaceChildren();
            const root = document.createElement('main'); root.className = 'view';
            document.body.append(root);
            const common = {capacity: 1, kind: 'individual', status: 'open'};
            const slots = [
                {...common, id: 1, start_at: '2026-11-16T10:00:00+09:00',
                 end_at: '2026-11-16T10:30:00+09:00', bookable: true,
                 managerState: 'free', remaining: 1},
                {...common, id: 2, start_at: '2026-11-16T11:00:00+09:00',
                 end_at: '2026-11-16T11:30:00+09:00', bookable: false,
                 managerState: 'reserved', staffBookingNames: '예약 학생',
                 reason: '마감', bookingCount: 1}
            ];
            root.append(renderCalendar({weekStart: '2026-11-16', selectedDay: '2026-11-16',
                mobileView: mode, dayCountMode: 'booked', slots, onSlot: () => {}, onDay: () => {}}));
        }""", mode)
        available = page.locator(".slot.open").first
        reserved = page.locator(".slot.reserved").first
        assert available.is_visible() and reserved.is_visible()
        color = "e => getComputedStyle(e).backgroundColor"
        assert available.evaluate(color) == "rgb(229, 239, 232)"
        assert reserved.evaluate(color) == "rgb(249, 232, 217)"
        assert "예약 학생" in reserved.inner_text()
        assert "마감" not in reserved.inner_text()
    finally:
        page.close()
