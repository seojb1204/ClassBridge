"""Approved calendar/menu layout, browser viewport checks (not a real phone)."""
import os

import pytest

from tests.e2e.test_e2e import Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('width', [360, 390, 1280])
def test_calendar_default_and_compact_controls(server, browser, width):  # noqa: F811
    base, _ = server
    s = Session(browser, base, 'prof@test.ac.kr', {'width': width, 'height': 900}, service_workers='block')
    p = s.page
    try:
        s.go('/slots')
        p.locator('.week-grid').wait_for()
        assert not p.get_by_role('heading', name='시간표', exact=True).is_visible()
        current_week = p.locator('.week-nav strong').inner_text()
        p.get_by_role('button', name='다음 주', exact=True).click()
        from playwright.sync_api import expect
        expect(p.locator('.week-nav strong')).not_to_have_text(current_week)
        p.get_by_role('button', name='이번 주로 이동', exact=True).click()
        expect(p.locator('.week-nav strong')).to_have_text(current_week)
        if width <= 720:
            assert p.locator('.calendar-view-switch').count() == 0
            assert p.locator('.schedule-fab').is_visible()
            menu_button = p.get_by_role('button', name='더보기 메뉴')
            menu_button.click()
            menu = p.locator('#nav')
            menu_box = menu.bounding_box()
            tab_box = p.locator('#mobile-tabs').bounding_box()
            assert 0 <= tab_box['y'] - menu_box['y'] - menu_box['height'] <= 12
            assert menu.get_by_text('설문·건의', exact=True).is_visible()
            assert menu.get_by_role('button', name='로그아웃').is_visible()
            p.keyboard.press('Escape')
            assert menu_button.get_attribute('aria-expanded') == 'false'
            assert menu_button.evaluate('e => e === document.activeElement')
        s.go('/slots')
        assert p.get_by_text('등록된 상담 시간만 예약할 수 있습니다.', exact=False).count() == 0
        p.route('**/api/slots/available-days', lambda r: r.fulfill(json=[
            {'date': '2026-11-17', 'count': 3}, {'date': '2026-11-18', 'count': 4},
            {'date': '2026-11-19', 'count': 4}]))
        p.reload()
        support = p.locator('.calendar-support')
        support.wait_for(state='attached')
        assert not support.is_visible()
        assert p.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        s.go('/slots/new')
        assert p.get_by_role('button', name='상담 시간', exact=True).is_visible()
        s.shot(f'calendar_usability_{width}')
    finally:
        s.close()
