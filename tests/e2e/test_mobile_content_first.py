"""Approved mobile priorities, short browser viewports, and refresh lifecycle."""

import os
from datetime import timedelta

import pytest
from playwright.sync_api import expect

from app.db import utcnow
from app.timeutil import today_kst
from tests.e2e.test_e2e import SHOTS, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E not set")


def visible_above_tabs(page, locator):
    box = locator.bounding_box()
    tabs = page.locator("#mobile-tabs").bounding_box()
    assert box and box["y"] >= 0
    assert box["y"] + box["height"] <= tabs["y"], (box, tabs)


@pytest.mark.parametrize("width,height", [(360, 640), (384, 640), (390, 700), (412, 700)])
@pytest.mark.parametrize("role", ["student", "prof", "admin"])
def test_first_action_and_flat_menu(server, browser, width, height, role):  # noqa: F811
    base, _ = server
    s = Session(browser, base, f"{role}@test.ac.kr", {"width": width, "height": height}, service_workers="block")
    p = s.page
    day = today_kst(utcnow()) + timedelta(days=7)
    day -= timedelta(days=day.weekday())
    date = day.isoformat()
    slot = dict(
        id=771,
        start_at=f"{date}T11:00:00+09:00",
        end_at=f"{date}T11:30:00+09:00",
        kind="individual",
        capacity=1,
        remaining=1,
        status="open",
        bookable=True,
        mine=False,
        location="m205",
    )
    booking = dict(id=772, slot=slot, status="booked", student_name="첫 예약 학생", student_number="20260001")
    p.route("**/api/slots?*", lambda r: r.fulfill(json=[slot]))
    p.route("**/api/slots/available-days", lambda r: r.fulfill(json=[dict(date=date, count=1)]))
    p.route("**/api/bookings/mine*", lambda r: r.fulfill(json=[]))
    p.route("**/api/bookings?*", lambda r: r.fulfill(json=[booking]))
    p.route("**/api/lectures/calendar?*", lambda r: r.fulfill(json=[]))
    p.route(
        "**/api/announcement",
        lambda r: r.fulfill(
            json={"announcement": dict(title="예약 안내", body="긴 공지입니다. " * 100, revision=7, published=True)}
        ),
    )
    p.route("**/api/suggestions/stats", lambda r: r.fulfill(json={"by_status": {"new": 0}}))
    p.route("**/api/surveys", lambda r: r.fulfill(json=[]))
    p.route("**/api/support/counts", lambda r: r.fulfill(json={"inbox": 0, "mine": 0}))
    p.reload()
    try:
        if role == "student":
            s.go("/booking")
            expect(p.get_by_role("button", name="목록형", exact=True)).to_have_attribute("aria-pressed", "true")
            visible_above_tabs(p, p.locator(".daily .card").first)
            expect(p.locator(".daily .card").first).to_contain_text("선택 ›")
            expect(p.locator(".daily .card").first).to_contain_text("장소: m205")
            assert p.locator(".announcement-panel").get_attribute("open") is None
            p.locator(".announcement-panel > summary").click()
            expect(p.locator(".announcement-panel .badge")).not_to_be_visible()
            p.locator(".announcement-panel > summary").click()
            p.get_by_role("button", name="달력형", exact=True).click()
            p.reload()
            expect(p.get_by_role("button", name="달력형", exact=True)).to_have_attribute("aria-pressed", "true")
            expect(p.locator(".announcement-panel .badge")).not_to_be_visible()
            p.get_by_role("button", name="목록형", exact=True).click()
        else:
            s.go("/bookings")
            p.get_by_role("link", name="오늘 예약 1건").wait_for()
            visible_above_tabs(p, p.locator(".mobile-bookings summary").first)
            p.get_by_role("link", name="오늘 예약 1건").click()
            expect(p.get_by_role("heading", name="오늘 상담 일정")).to_be_visible()
            s.go("/bookings")
        p.screenshot(path=str(SHOTS / f"content-first-{role}-{width}x{height}.png"))
        p.get_by_role("button", name="더보기 메뉴").click()
        nav = p.locator("#nav")
        assert nav.locator(".bottom-tab-duplicate:visible").count() == 0
        target = nav.get_by_role("link", name="익명 건의" if role == "student" else "개인 설정", exact=True)
        expect(target).to_be_visible()
        target.click()
        if role != "student":
            daily = p.get_by_label("평일 상담 요약 받기")
            daily.uncheck()
            expect(p.get_by_label("받을 시각 (한국시간)")).to_be_disabled()
            daily.check()
            expect(p.get_by_label("받을 시각 (한국시간)")).to_be_enabled()
        assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    finally:
        s.close()


def test_today_states_and_survey_closed_copy(server, browser):  # noqa: F811
    base, _ = server
    s = Session(browser, base, "admin@test.ac.kr", {"width": 384, "height": 640}, service_workers="block")
    p = s.page
    p.route("**/api/bookings?*", lambda r: r.fulfill(json=[]))
    p.route("**/api/suggestions/stats", lambda r: r.fulfill(json={"by_status": {"new": 0}}))
    p.route("**/api/surveys", lambda r: r.fulfill(json=[]))
    p.route("**/api/support/counts", lambda r: r.fulfill(json={"inbox": 0, "mine": 0}))
    s.go("/bookings")
    expect(p.locator(".staff-today")).to_contain_text("오늘 확인할 항목 없음")
    p.screenshot(path=str(SHOTS / "today-zero.png"))
    p.route("**/api/suggestions/stats", lambda r: r.fulfill(json={}))
    p.get_by_role("button", name="오늘 할 일 다시 확인").click()
    expect(p.locator(".staff-today")).to_contain_text("일부 항목 확인 필요")
    p.get_by_text("확인하지 못한 항목", exact=True).click()
    expect(p.get_by_text("새 건의 · 확인 불가")).to_be_visible()
    p.screenshot(path=str(SHOTS / "today-partial.png"))
    s.close()
    s = Session(browser, base, "survey-mobile@test.ac.kr", {"width": 384, "height": 640}, service_workers="block")
    p = s.page
    p.route(
        "**/api/surveys/student/list",
        lambda r: r.fulfill(
            json=[
                dict(
                    id=1,
                    title="설문",
                    course_name="기업가정신",
                    description="기업가정신",
                    is_open=False,
                    closes_at=None,
                    access_mode="anonymous",
                )
            ]
        ),
    )
    s.go("/surveys")
    expect(p.get_by_text("현재 참여 가능한 설문이 없습니다.")).to_be_visible()
    p.get_by_text("지난 설문·참여 내역 1건").click()
    expect(p.get_by_text("응답 접수가 종료되었습니다")).to_be_visible()
    assert p.get_by_text("기업가정신", exact=True).count() == 1
    assert "교수자가 직접 마감합니다" not in p.locator("#view").inner_text()
    s.close()


def test_inbox_timer_preserves_scroll_filter_and_stops(server, browser):  # noqa: F811
    base, _ = server
    s = Session(browser, base, "prof@test.ac.kr", {"width": 384, "height": 640}, service_workers="block")
    p = s.page
    calls = []

    def inbox(route):
        calls.append(route.request.url)
        route.fulfill(
            json={
                "items": [
                    dict(
                        id=i,
                        title="예약 접수 알림",
                        body="예약 학생 · 11:00–11:30",
                        read=False,
                        url="#/bookings",
                        arrived_at="2026-11-23T10:00:00+09:00",
                    )
                    for i in range(30, 0, -1)
                ],
                "unread": 30,
            }
        )

    p.route("**/api/inbox?*", inbox)
    p.clock.install()
    s.go("/inbox")
    expect(p.locator(".inbox-item")).to_have_count(30)
    visible_above_tabs(p, p.locator(".inbox-item").first)
    p.screenshot(path=str(SHOTS / "inbox-first-384x640.png"))
    p.get_by_role("button", name="미읽음만").click()
    p.evaluate("scrollTo(0, 500)")
    before = len(calls)
    p.clock.run_for(61000)
    p.wait_for_timeout(100)
    assert len(calls) > before
    assert all("unread_only=true" in url for url in calls[before:])
    assert abs(p.evaluate("scrollY") - 500) <= 2
    # The watcher must not replace a dialog, and is removed on route change.
    p.evaluate(
        "async () => { const {modal} = await import('/static/js/ui.js'); "
        "void modal('확인', document.createElement('p'), [{label:'닫기',value:null}]); }"
    )
    before = len(calls)
    p.clock.run_for(61000)
    assert len(calls) == before
    expect(p.get_by_role("dialog", name="확인")).to_be_visible()
    p.get_by_role("button", name="닫기", exact=True).click()
    s.go("/bookings")
    before = len(calls)
    p.clock.run_for(61000)
    assert len(calls) == before
    s.close()
