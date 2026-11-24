"""Approved staff screen: retained bell, week navigation, timetable and floating registration."""
import os

import pytest
from playwright.sync_api import expect

from tests.conftest import future_day
from tests.e2e.test_e2e import SHOTS, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E not set")


@pytest.mark.parametrize("role", ["prof", "admin"])
@pytest.mark.parametrize("width,height", [(360, 640), (390, 700)])
def test_minimal_calendar_bell_and_unlinked_registration(server, browser, role, width, height):  # noqa: F811
    base, _ = server
    session = Session(browser, base, f"{role}@test.ac.kr", {"width": width, "height": height}, service_workers="block")
    p = session.page
    session.go("/slots")
    bell = p.locator('.topbar [aria-controls="inbox-popover"]')
    expect(bell).to_be_visible()
    bell.click()
    expect(p.locator('#inbox-popover')).to_be_visible()
    bell.click()
    expect(p.locator('.week-nav')).to_be_visible()
    expect(p.locator('.week-grid')).to_be_visible()
    expect(p.locator('.calendar-support')).to_be_hidden()
    assert p.locator('.calendar-tools:visible, .calendar-view-switch, .calendar-help').count() == 0
    fab = p.get_by_role('link', name='+ 일정 등록', exact=True)
    box, tabs = fab.bounding_box(), p.locator('#mobile-tabs').bounding_box()
    assert box['height'] >= 44 and box['y'] + box['height'] < tabs['y']
    p.screenshot(path=str(SHOTS / f'minimal-{role}-{width}.png'))
    fab.click()
    sheet = p.get_by_role('dialog', name='일정 등록', exact=True)
    expect(sheet).to_be_visible()
    p.locator('.registration-tabs').get_by_role('button', name='예약 등록', exact=True).click()
    form = p.locator('.staff-booking-form')
    expect(form.get_by_label('학생 계정 연결 (선택)', exact=True)).to_have_value('')
    form.get_by_label('학생 이름 *', exact=True).fill(f'미연결 검증 {role} {width}')
    # Each case has its own future day; no changes to production accounts/data.
    day = future_day(35 + (0 if role == 'prof' else 14) + (0 if width == 360 else 7))
    form.get_by_label('날짜', exact=True).fill(day.isoformat())
    form.get_by_label('시작', exact=True).fill('16:00')
    form.get_by_label('종료', exact=True).fill('16:30')
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
    p.screenshot(path=str(SHOTS / f'registration-{role}-{width}.png'))
    form.get_by_role('button', name='예약 등록', exact=True).click()
    session.toast('예약을 등록했습니다')
    expect(sheet).to_have_count(0)
    expect(p.locator('.week-grid')).to_contain_text(f'미연결 검증 {role} {width}')
    expect(bell).to_be_visible()
    fab.click()
    expect(sheet).to_be_visible()
    p.keyboard.press('Escape')
    expect(sheet).to_have_count(0)
    session.close()
