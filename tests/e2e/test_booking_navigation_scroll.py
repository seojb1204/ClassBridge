"""Mobile date navigation must retain both page and calendar scroll positions."""
import os

import pytest
from playwright.sync_api import expect

from tests.e2e.test_e2e import MOBILE, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E not set")


def test_mobile_booking_week_navigation_keeps_scroll(server, browser):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", MOBILE, service_workers="block")
    p = staff.page
    staff.go("/slots")
    p.locator('.week-nav').wait_for()
    p.wait_for_load_state('networkidle')
    for name in ['다음 주', '이전 주', '다음 주', '이번 주로 이동']:
        p.evaluate("""() => {
            const nav = document.querySelector('.week-nav').getBoundingClientRect();
            const header = document.querySelector('.topbar').getBoundingClientRect();
            window.scrollTo(0, window.scrollY + nav.top - header.height - 24);
        }""")
        p.wait_for_timeout(100)
        before = p.evaluate('scrollY')
        assert before > 0
        p.get_by_role('button', name=name, exact=True).click()
        p.wait_for_timeout(350)
        assert abs(p.evaluate('scrollY') - before) < 3
    staff.close()


def test_delegate_booking_moved_to_registration(server, browser):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", MOBILE, service_workers="block")
    p = staff.page
    staff.go('/bookings')
    expect(p.get_by_role('button', name='학생 대신 예약', exact=True)).to_have_count(0)
    p.get_by_role('button', name='예약 목록', exact=True).click()
    expect(p.get_by_role('button', name='학생 대신 예약', exact=True)).to_have_count(0)
    staff.go('/slots/new')
    student = {'id': 710, 'name': '테스트 학생', 'email': 'test@example.invalid'}
    p.route('**/api/students', lambda r: r.fulfill(json=[student]))
    p.get_by_role('button', name='학생 대신 예약', exact=True).click()
    expect(p.locator('#modal-root')).to_contain_text('학생 선택')
    p.locator('#modal-root').get_by_role('button', name='취소', exact=True).click()
    expect(p.locator('#slot-create-panel')).to_be_visible()
    expect(p.get_by_role('heading', name='상담·강의 등록', exact=True)).to_be_visible()
    staff.close()


@pytest.mark.parametrize('reduced', [False, True])
def test_booking_swipe_uses_connected_280ms_slide(server, browser, reduced):  # noqa: F811
    base, _ = server

    class TouchBrowser:
        def new_context(self, **kwargs):
            return browser.new_context(**kwargs, is_mobile=True, has_touch=True,
                                       reduced_motion='reduce' if reduced else 'no-preference')

    staff = Session(TouchBrowser(), base, 'prof@test.ac.kr', MOBILE, service_workers='block')
    p = staff.page
    staff.go('/slots')
    p.wait_for_load_state('networkidle')
    p.evaluate('''() => {
        window.slideDurations = [];
        const original = Element.prototype.animate;
        Element.prototype.animate = function(frames, options) {
            window.slideDurations.push(options.duration);
            return original.call(this, frames, options);
        };
    }''')
    wrap = p.locator('.mobile-grid-wrap')
    wrap.scroll_into_view_if_needed()
    before = p.locator('.week-nav strong').inner_text()
    box = wrap.bounding_box()
    x, y = box['x'] + box['width'] - 25, box['y'] + min(100, box['height'] / 2)
    cdp = p.context.new_cdp_session(p)
    cdp.send('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 1})
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]})
    for step in range(1, 9):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove',
                                           'touchPoints': [{'x': x - step * 15, 'y': y}]})
        p.wait_for_timeout(25)
    transform = wrap.locator('.week-grid').evaluate('e => getComputedStyle(e).transform')
    if reduced:
        assert transform == 'none'
    else:
        assert abs(float(transform.split(',')[4]) + 120) < 2
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    expect(p.locator('.week-nav strong')).not_to_have_text(before)
    p.wait_for_timeout(500)
    assert p.evaluate('window.slideDurations') == ([] if reduced else [280, 280])
    expect(p.locator('.week-slide-outgoing')).to_have_count(0)
    assert not wrap.evaluate('e => e.inert')
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
    cdp.detach()
    staff.close()
