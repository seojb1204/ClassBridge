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


@pytest.mark.parametrize("email,path", [
    ("prof@test.ac.kr", "/slots"), ("admin@test.ac.kr", "/slots"),
    ("grid-student@test.ac.kr", "/booking"),
])
@pytest.mark.parametrize("viewport", [MOBILE, {"width": 360, "height": 640}])
def test_mobile_calendar_week_three_list_and_details(server, browser, email, path, viewport):  # noqa: F811
    from datetime import date, timedelta
    from urllib.parse import parse_qs, urlparse

    from playwright.sync_api import expect

    base, _ = server
    session = Session(browser, base, email, viewport, service_workers="block")
    p = session.page

    def events(route, lecture=False):
        start = date.fromisoformat(parse_qs(urlparse(route.request.url).query)["start"][0])
        start -= timedelta(days=start.weekday())
        rows = []
        for i in range(7):
            day = (start + timedelta(days=i)).isoformat()
            row = {"id": (98000 if lecture else 97000) + i,
                   "start_at": f"{day}T{'12:05' if lecture else '10:00'}:00+09:00",
                   "end_at": f"{day}T{'12:50' if lecture else '10:30'}:00+09:00",
                   "kind": "individual", "capacity": 1, "remaining": 1, "status": "open",
                   "bookable": True, "mine": False, "location": "시험 강의실", "note": "", "reason": ""}
            if lecture:
                row.update(event_type="lecture", title=f"격자 강의 {i}")
            rows.append(row)
        route.fulfill(json=rows)

    p.route("**/api/slots?*", lambda route: events(route))
    p.route("**/api/lectures?*", lambda route: events(route, lecture=True))
    p.reload()
    session.go(path)
    p.locator(".calendar-week .week-grid").wait_for()
    assert p.get_by_role("button", name="주간", exact=True).get_attribute("aria-pressed") == "true"
    assert p.locator(".week-grid .day-head").count() == 7
    expect(p.locator(".week-grid .slot.open")).to_have_count(7)
    assert p.locator(".week-grid .slot.open").first.bounding_box()["height"] >= 44
    if path == "/slots":
        expect(p.locator(".week-grid .slot.lecture")).to_have_count(7)
        lecture = p.locator('.week-grid [data-slot-id="98000"]')
        assert lecture.evaluate("el => el.style.marginTop") == "9px"
        lecture.click()
        assert p.locator(".modal").get_by_label("강의명", exact=True).input_value() == "격자 강의 0"
        p.keyboard.press("Escape")
    else:
        p.locator(".week-grid .slot.open").last.click()
        p.locator(".modal").wait_for()
        p.keyboard.press("Escape")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    session.shot(f"calendar_week_{email.split('@')[0]}_{viewport['width']}")
    before = p.locator(".week-grid .day-head").first.inner_text()
    p.get_by_role("button", name="다음 주", exact=True).click()
    expect(p.locator(".week-grid .day-head").first).not_to_have_text(before)
    assert p.locator(".week-grid .day-head").count() == 7
    p.get_by_role("button", name="3일", exact=True).click()
    p.locator(".calendar-three").wait_for()
    assert p.locator(".week-grid .day-head").count() == 3
    assert p.locator(".week-grid .slot.open").count() == 3
    p.get_by_role("button", name="다음 3일", exact=True).click()
    p.get_by_role("button", name="이전 3일", exact=True).wait_for(state="visible")
    expect(p.get_by_role("button", name="이전 3일", exact=True)).to_be_enabled()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    session.shot(f"calendar_three_{email.split('@')[0]}_{viewport['width']}")
    p.get_by_role("button", name="목록", exact=True).click()
    p.locator(".day-chips").wait_for()
    assert p.locator(".day-chips .chip").count() == 7
    p.locator(".day-chips .chip").last.click()
    expect(p.locator(".day-chips .chip").last).to_have_attribute("aria-selected", "true")
    expect(p.locator(".daily .card.slot.open").first).to_be_visible()
    assert p.locator(".daily .card.slot.open").count() == 1
    if path == "/slots":
        assert p.locator(".daily .card.slot.lecture").count() == 1
    assert p.locator(".daily .card.slot.open").first.bounding_box()["height"] >= 44
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    session.shot(f"calendar_list_{email.split('@')[0]}_{viewport['width']}")
    p.get_by_role("button", name="주간", exact=True).click()
    p.locator(".calendar-week").wait_for()
    assert p.locator(".week-grid .day-head").count() == 7
    session.close()


@pytest.mark.parametrize("mode", ["주간", "3일"])
@pytest.mark.parametrize("width", [360, 390])
def test_mobile_calendar_scroll_chains_at_vertical_edges(server, browser, mode, width):  # noqa: F811
    from datetime import date, timedelta
    from urllib.parse import parse_qs, urlparse

    from playwright.sync_api import expect

    base, _ = server
    class TouchBrowser:
        def new_context(self, **kwargs):
            return browser.new_context(**kwargs, is_mobile=True, has_touch=True)

    session = Session(TouchBrowser(), base, "prof@test.ac.kr", {"width": width, "height": 640}, service_workers="block")
    p = session.page
    def tall_calendar(route):
        start = date.fromisoformat(parse_qs(urlparse(route.request.url).query)["start"][0])
        start -= timedelta(days=start.weekday())
        route.fulfill(json=[{
            "id": 99000 + i, "start_at": f"{start + timedelta(days=i)}T09:00:00+09:00",
            "end_at": f"{start + timedelta(days=i)}T17:00:00+09:00",
            "kind": "individual", "capacity": 1, "remaining": 1, "status": "open",
            "bookable": True, "mine": False, "location": "", "note": "", "reason": "",
        } for i in range(7)])

    p.route("**/api/slots?*", tall_calendar)
    p.route("**/api/lectures?*", lambda route: route.fulfill(json=[]))
    session.go("/bookings")
    session.go("/slots")
    p.get_by_role("button", name=mode, exact=True).click()
    grid = p.locator(".mobile-grid-wrap")
    expect(grid.locator(".slot")).to_have_count(7 if mode == "주간" else 3)
    p.wait_for_timeout(500)
    # Keep both outer directions scrollable independently of fixture event count.
    p.evaluate("""() => {
        const spacer = document.createElement('div');
        spacer.style.height = '1200px'; document.body.append(spacer);
    }""")
    assert grid.evaluate("e => getComputedStyle(e).overscrollBehaviorY") == "auto"
    assert grid.evaluate("e => getComputedStyle(e).overscrollBehaviorX") == "auto"
    assert grid.evaluate("e => e.scrollHeight > e.clientHeight")
    cdp = p.context.new_cdp_session(p)
    cdp.send("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1})
    for direction in (1, -1):
        grid.evaluate("""(e, down) => {
            window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - 100);
            e.scrollTop = down ? e.scrollHeight : 0;
        }""", direction == 1)
        p.wait_for_timeout(500)
        before = p.evaluate("scrollY")
        box = grid.bounding_box()
        # Dispatch native touch input with touch emulation explicitly enabled.
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        p.wait_for_timeout(80)
        for step in range(1, 11):
            cdp.send("Input.dispatchTouchEvent", {
                "type": "touchMove", "touchPoints": [{"x": x, "y": y - direction * step * 14}],
            })
            p.wait_for_timeout(40)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        p.wait_for_timeout(800)
        diagnostics = {
            "direction": direction, "before": before, "after": p.evaluate("scrollY"),
            "inner": grid.evaluate("e => [e.scrollTop, e.scrollHeight, e.clientHeight]"),
            "hit": p.evaluate("([x,y]) => document.elementFromPoint(x,y)?.outerHTML", [x, y]),
            "viewport": p.evaluate("({width:innerWidth, height:innerHeight, visual:visualViewport.toJSON?.(), scrollHeight:document.documentElement.scrollHeight})"),  # noqa: E501
            "box": box,
            "chain": grid.evaluate("e => {let a=[];for(;e;e=e.parentElement){let c=getComputedStyle(e);a.push([e.tagName,e.className,c.overflowY,c.overscrollBehaviorY,c.touchAction,e.scrollTop,e.scrollHeight,e.clientHeight])}return a}"),  # noqa: E501
        }
        print(diagnostics)
        assert (p.evaluate("scrollY") - before) * direction > 20
    expect(p.get_by_role("button", name=mode, exact=True)).to_have_attribute("aria-pressed", "true")
    cdp.detach()
    session.close()
