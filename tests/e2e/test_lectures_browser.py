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
    dialog = p.locator(".lecture-create-form")
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


@pytest.mark.parametrize("email", ["prof@test.ac.kr", "admin@test.ac.kr"])
@pytest.mark.parametrize("viewport", [MOBILE, {"width": 360, "height": 640}])
def test_lecture_discoverable_before_notice(server, browser, email, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, email, viewport, service_workers="block")
    p = staff.page
    staff.go("/slots")
    button = p.get_by_role("button", name="+ 강의 추가", exact=True)
    box = button.bounding_box()
    nav = p.locator("#mobile-tabs").bounding_box()
    assert box and nav and box["y"] + box["height"] < nav["y"]
    button.click()
    p.locator(".lecture-create-form").wait_for()
    assert p.get_by_role("button", name="강의", exact=True).get_attribute("aria-pressed") == "true"
    p.get_by_label("강의명", exact=True).fill("취소할 입력")
    p.get_by_role("button", name="상담 가능 시간", exact=True).click()
    assert p.get_by_role("button", name="등록 미리보기", exact=True).is_visible()
    assert p.locator(".lecture-create-form").count() == 0
    p.get_by_role("button", name="강의", exact=True).click()
    assert p.get_by_label("강의명", exact=True).input_value() == "취소할 입력"
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert p.locator('meta[name="theme-color"]').get_attribute("content") == "#f7f3ec"
    manifest = p.request.get(base + "/static/manifest.webmanifest").json()
    assert manifest["theme_color"] == manifest["background_color"] == "#f7f3ec"
    staff.shot("registration_mobile_" + email.split("@")[0] + "_" + str(viewport["width"]))
    staff.close()
