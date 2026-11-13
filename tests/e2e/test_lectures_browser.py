import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_staff_manual_lecture_same_calendar(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    p = staff.page
    staff.go("/slots")
    p.get_by_role("button", name="+ 강의 추가", exact=True).click()
    dialog = p.locator(".modal")
    dialog.get_by_label("강의명", exact=True).fill("수동 강의 브라우저 " + str(viewport["width"]))
    dialog.get_by_label("시작 (한국 시간)", exact=True).fill("20:05" if viewport == PC else "21:05")
    dialog.get_by_label("종료 (한국 시간)", exact=True).fill("20:50" if viewport == PC else "21:50")
    dialog.get_by_role("button", name="강의 저장", exact=True).click()
    p.locator(".slot.lecture").filter(has_text=str(viewport["width"])).wait_for()
    if viewport == PC:
        placement = p.locator(".slot.lecture").filter(has_text=str(viewport["width"])).evaluate(
            "el => ({row: el.style.gridRowStart, margin: el.style.marginTop})")
        assert placement["row"].isdigit(), placement
        assert placement["margin"] == "7px", placement
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    staff.shot("lectures_" + str(viewport["width"]))
    p.locator(".slot.lecture").filter(has_text=str(viewport["width"])).click()
    dialog = p.locator(".modal")
    assert dialog.get_by_label("강의명", exact=True).input_value().endswith(str(viewport["width"]))
    dialog.get_by_role("button", name="강의 삭제", exact=True).click()
    p.get_by_role("button", name="아니오", exact=True).click()
    assert p.locator(".modal").count() == 0
    p.locator(".slot.lecture").filter(has_text=str(viewport["width"])).click()
    p.locator(".modal").get_by_role("button", name="강의 삭제", exact=True).click()
    p.get_by_role("button", name="예, 삭제", exact=True).click()
    p.locator(".modal").wait_for(state="detached")
    assert p.locator(".slot.lecture").filter(has_text=str(viewport["width"])).count() == 0
    staff.close()
