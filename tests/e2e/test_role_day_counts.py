"""Role-specific count semantics and mobile/desktop navigation smoke checks."""
import os
import re
from datetime import timedelta

import pytest
from playwright.sync_api import expect

from app.db import utcnow
from app.timeutil import today_kst
from tests.e2e.test_e2e import SHOTS, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('role', ['student', 'prof', 'admin'])
@pytest.mark.parametrize('width', [360, 390, 1366])
def test_role_counts_and_navigation(server, browser, role, width):  # noqa: F811
    base, _ = server
    s = Session(browser, base, f'{role}@test.ac.kr', {'width': width, 'height': 844}, service_workers='block')
    p = s.page
    today = today_kst(utcnow())
    day = (today - timedelta(days=today.weekday())).isoformat()
    def slot(id, hour, capacity, remaining, bookable):
        return dict(id=id, start_at=f'{day}T{hour}:00:00+09:00', end_at=f'{day}T{hour}:30:00+09:00',
                    kind='group' if capacity > 1 else 'individual', capacity=capacity, remaining=remaining,
                    status='open', bookable=bookable, mine=False, location='상담실', note='', reason='')
    slots = [slot(991, '10', 1, 1, True), slot(992, '11', 5, 2, True), slot(993, '12', 1, 0, False)]
    bookings = [dict(id=i, slot=slots[1] if i < 4 else slots[2], status='booked', student_name=f'가상학생{i}',
                     applicant_name=f'가상학생{i}', professor_note='', consultation_type='career',
                     consultation_mode='in_person')
                for i in range(1, 5)]
    p.route('**/api/slots?*', lambda r: r.fulfill(json=slots))
    p.route('**/api/slots/available-days', lambda r: r.fulfill(json=[{'date': day, 'count': 2}]))
    p.route('**/api/bookings?*', lambda r: r.fulfill(json=[] if role == 'student' else bookings))
    p.route('**/api/bookings/mine*', lambda r: r.fulfill(json=[]))
    p.route('**/api/lectures/calendar?*', lambda r: r.fulfill(json=[]))
    p.route('**/api/lectures?*', lambda r: r.fulfill(json=[]))
    p.reload()  # Reload after routing to replace the initial authenticated page data.
    s.go('/booking' if role == 'student' else '/slots')
    p.get_by_role('button', name='이번 주로 이동', exact=True).click()
    if width <= 720 and role == 'student':
        p.get_by_role('button', name='목록형', exact=True).click()
        chips = p.locator('.day-chips')
        chips.wait_for()
        first = chips.get_by_role('tab').first
        expected = '예약 가능 2건' if role == 'student' else '예약 4명'
        expect(first).to_have_attribute('aria-label', re.compile(re.escape(expected) + '$'))
        assert first.locator('em').inner_text() == ('2' if role == 'student' else '4명')
        first.click()
        assert p.locator('.daily .cards .card').count() == 3
        assert p.locator('#mobile-tabs').is_visible()
    else:
        p.get_by_role('grid', name='달력형 주간 시간표').wait_for()
    assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
    s.shot(f'role-audit-01-{role}-{width}-calendar')
    if width <= 720:
        p.get_by_role('button', name='더보기 메뉴', exact=True).click()
        expect(p.locator('#nav')).to_be_visible()
        if role == 'admin':
            expect(p.locator('#nav').get_by_role('link', name='계정·권한', exact=True)).to_be_visible()
        elif role == 'prof':
            assert p.locator('#nav a[href="#/admin/users"]').count() == 0
        else:
            expect(p.locator('#nav').get_by_role('link', name='익명 건의', exact=True)).to_be_visible()
            assert p.locator('#nav a[href="#/slots"]').count() == 0
        s.shot(f'role-audit-menu-{role}-{width}')
        p.locator('#nav').press('Escape')
        expect(p.get_by_role('button', name='더보기 메뉴')).to_have_attribute('aria-expanded', 'false')
    routes = ['/my-bookings', '/surveys', '/suggestions', '/help'] if role == 'student' else [
        '/bookings', '/slots/new', '/staff/insights', '/surveys', '/suggestions', '/personal', '/help']
    if role == 'admin':
        routes += ['/admin/users', '/admin/settings', '/admin/audit']
    for index, route in enumerate(routes, 2):
        p.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        s.go(route)
        assert p.evaluate("scrollY") == 0, route
        assert p.locator('#view').inner_text().strip()
        assert p.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
        s.shot(f'role-audit-{index:02}-{role}-{width}-{route.strip("/").replace("/", "-")}')
        if width <= 720:
            p.screenshot(path=str(SHOTS / f'role-viewport-{role}-{width}-{route.strip("/").replace("/", "-")}.png'))
        if route == '/admin/users':
            p.get_by_role('searchbox', name='이름·이메일 검색').fill('student@test.ac.kr')
            expect(p.locator('.user-table tbody tr:visible')).to_have_count(1)
            p.get_by_role('searchbox', name='이름·이메일 검색').fill('')
            p.get_by_label('역할 필터').select_option('professor')
            expect(p.locator('.user-table tbody tr:visible')).to_have_count(1)
            p.get_by_label('역할 필터').select_option('')
        if route == '/bookings':
            panel = p.locator('.staff-today')
            panel.get_by_role('link', name='오늘 예약 4건', exact=True).click()
            expect(p.get_by_role('heading', name='오늘 상담 일정', exact=True)).to_be_visible()
            if width <= 720:
                expect(p.locator('#mobile-tabs a[href="#/bookings"]')).to_have_attribute('aria-current', 'page')
            p.get_by_role('link', name='전체 예약 관리', exact=True).click()
            expect(p.get_by_role('heading', name='예약 관리', exact=True)).to_be_visible()
    s.close()
