"""Same reservation controls and draft protection on desktop and mobile."""
import os

import pytest

from tests.e2e.test_e2e import browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("width", [390, 1280])
def test_shared_editor_preserves_notes_and_allows_outcome_correction(server, browser, width):  # noqa: F811
    base, _ = server
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.goto(base + "/static/offline.html")
    page.add_style_tag(url=base + "/static/css/app.css")
    writes = []

    def write(route):
        writes.append((route.request.url, route.request.post_data_json))
        route.fulfill(json={})

    page.route("**/api/bookings/*/note", write)
    page.route("**/api/bookings/*/outcome", write)
    page.evaluate("""async () => {
      document.body.innerHTML = '<main id="view"></main><div id="modal-root"></div><div id="toasts"></div>';
      const {showStaffSlot} = await import('/static/js/views/prof-bookings.js');
      const slot = {id: 99, start_at: '2026-01-01T10:00:00+09:00', end_at: '2026-01-01T10:20:00+09:00', capacity: 2};
      const bookings = [{id: 1, slot, status: 'expired', student_name: '학생 하나', professor_note: '기존 기록'},
        {id: 2, slot, status: 'no_show', student_name: '학생 둘', professor_note: '둘의 기록'}];
      void showStaffSlot(document.querySelector('main'), slot, bookings, false, () => {});
    }""")
    dialog = page.get_by_role("dialog", name="예약·상담 상세")
    assert dialog.locator("textarea").input_value() == "기존 기록"
    assert dialog.get_by_role("button", name="상담 완료", exact=True).is_visible()
    assert dialog.get_by_role("button", name="미참석", exact=True).is_visible()
    dialog.locator("textarea").fill("저장 전 기록")
    page.once("dialog", lambda d: d.dismiss())
    dialog.get_by_label("학생 선택").select_option("2")
    assert dialog.get_by_label("학생 선택").input_value() == "1"
    assert dialog.locator("textarea").input_value() == "저장 전 기록"
    page.once("dialog", lambda d: d.dismiss())
    page.keyboard.press("Escape")
    assert dialog.is_visible()
    dialog.get_by_role("button", name="기록 저장", exact=True).click()
    page.get_by_text("상담 기록을 저장했습니다.", exact=True).wait_for()
    assert writes[-1][1] == {"note": "저장 전 기록"}
    dialog.get_by_label("학생 선택").select_option("2")
    assert dialog.locator("textarea").input_value() == "둘의 기록"
    assert dialog.get_by_role("button", name="미참석", exact=True).count() == 0
    dialog.get_by_role("button", name="상담 완료", exact=True).click()
    page.get_by_text("상담 결과를 저장했습니다.", exact=True).wait_for()
    assert writes[-1][1] == {"outcome": "completed"}
    assert dialog.get_by_role("button", name="미참석", exact=True).is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.close()
