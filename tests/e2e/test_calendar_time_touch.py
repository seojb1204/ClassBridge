"""A blank time cell only pre-fills the existing role-specific flow, never saves."""
import os

import pytest
from playwright.sync_api import expect

from tests.e2e.test_e2e import Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("email", ["prof@test.ac.kr", "admin@test.ac.kr"])
def test_empty_time_prefills_both_registration_kinds(server, browser, email):  # noqa: F811
    base, _ = server
    session = Session(browser, base, email, {"width": 390, "height": 844}, service_workers="block")
    p = session.page
    p.route("**/api/slots?*", lambda r: r.fulfill(json=[]))
    p.route("**/api/lectures?*", lambda r: r.fulfill(json=[]))
    writes = []
    p.on("request", lambda r: writes.append(r.url) if r.method in ("POST", "PATCH", "PUT", "DELETE") else None)
    session.go("/slots")
    cell = p.locator(".calendar-time-cell").first
    cell.wait_for()
    expected_date = p.locator(".calendar-grid-title").inner_text().split(" – ")[0]
    # Pick 09:15 within the hourly hit area, not its keyboard default (09:00).
    box = cell.bounding_box()
    cell.click(position={"x": box["width"] / 2, "y": box["height"] * .375})
    expect(p.get_by_role("heading", name="상담·강의 등록")).to_be_visible()
    expect(p.get_by_label("시작", exact=True)).to_have_value("09:15")
    expect(p.get_by_label("종료", exact=True)).to_have_value("09:45")
    picked_date = p.get_by_label("날짜(시작일)", exact=True).input_value()
    assert picked_date[5:7].lstrip("0") + "월" in expected_date
    p.get_by_role("button", name="강의", exact=True).click()
    expect(p.get_by_label("날짜", exact=True)).to_have_value(picked_date)
    expect(p.get_by_label("시작 (한국 시간)", exact=True)).to_have_value("09:15")
    expect(p.get_by_label("종료 (한국 시간)", exact=True)).to_have_value("09:45")
    assert not writes
    session.close()


def test_student_blank_time_does_not_create_booking(server, browser):  # noqa: F811
    base, _ = server
    session = Session(browser, base, "grid-student@test.ac.kr", {"width": 390, "height": 844}, service_workers="block")
    p = session.page
    p.route("**/api/slots?*", lambda r: r.fulfill(json=[]))
    session.go("/booking")
    writes = []
    p.on("request", lambda r: writes.append(r.url) if r.method in ("POST", "PATCH", "PUT", "DELETE") else None)
    p.locator(".calendar-time-cell").first.focus()
    p.keyboard.press("Enter")
    message = "이 시간에는 예약 가능한 상담이 없습니다. 등록된 상담 시간을 선택해 주세요."
    expect(p.get_by_text(message, exact=True)).to_be_visible()
    assert p.url.endswith("#/booking")
    assert not writes
    assert p.locator(".lecture-create-form").count() == 0
    session.close()
