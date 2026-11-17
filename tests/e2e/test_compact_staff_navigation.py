"""Approved compact UI keeps calendar and all staff destinations."""
import os

import pytest

from tests.e2e.test_e2e import Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('width', [1280, 933, 390])
def test_staff_menu_calendar_and_activity_rows(server, browser, width):  # noqa: F811
    base, _ = server
    s = Session(browser, base, 'admin@test.ac.kr', {'width': width, 'height': 900}, service_workers='block')
    page = s.page
    try:
        s.go('/bookings')
        # The existing calendar control and calendar itself are not replaced by a list.
        page.get_by_role('button', name='주간 예약 시간표', exact=True).click()
        page.locator('.week-wrap').wait_for(state='visible')
        if width <= 720:
            page.get_by_role('button', name='더보기 메뉴').click()
            assert page.locator('#nav summary').first.evaluate('e => e === document.activeElement')
        menu = page.locator('#nav')
        menu.locator('summary').filter(has_text='예약 관리').click()
        assert menu.get_by_role('link', name='상담 시간', exact=True).is_visible()
        page.keyboard.press('Escape')
        assert menu.locator('.nav-group').first.evaluate('e => !e.open')
        menu.locator('summary').filter(has_text='상담 정보').click()
        assert menu.get_by_role('link', name='내 알림', exact=True).is_visible()
        menu.locator('summary').filter(has_text='관리').last.click()
        assert menu.get_by_role('link', name='계정·권한').is_visible()
        if width <= 720:
            page.get_by_role('button', name='더보기 메뉴').click()
        event = {'id': 30, 'booking_id': 7, 'action': 'cancel', 'actor_name': '테스트 학생',
                 'student_name': '예약 학생', 'actor_is_student': True,
                 'at': '2026-11-17T01:02:03Z', 'start_at': '2026-11-18T04:00:00Z',
                 'status': 'cancelled', 'detail': '상세 내용'}
        page.route('**/api/staff/booking-events?*', lambda r: r.fulfill(json={'items': [event], 'next_before_id': None}))
        page.get_by_role('button', name='예약 활동 기록', exact=True).click()
        row = page.locator('.activity-table tbody tr')
        row.wait_for()
        assert row.locator('td').count() == 5
        assert row.get_by_text('예약 학생', exact=True).is_visible()
        if width > 720:
            boxes = [row.locator('td').nth(i).bounding_box() for i in range(5)]
            assert len({round(b['y']) for b in boxes}) == 1
        row.get_by_text('상세 보기').click()
        assert row.get_by_text('기록 내용: 상세 내용').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        s.shot(f'compact_staff_{width}')
    finally:
        s.close()


@pytest.mark.parametrize('email,staff', [('prof@test.ac.kr', True), ('compact-student@test.ac.kr', False)])
def test_role_navigation_and_disabled_features(server, browser, email, staff):  # noqa: F811
    base, _ = server
    s = Session(browser, base, email, {'width': 1280, 'height': 900}, service_workers='block')
    page = s.page
    try:
        def me_without_optional_features(route):
            response = route.fetch()
            data = response.json()
            data['features'] = {'surveys': False, 'suggestions': False}
            route.fulfill(json=data)
        page.route('**/api/me', me_without_optional_features)
        page.reload()
        page.wait_for_selector('body[data-ready]:not([data-ready=""])', state='attached')
        nav = page.locator('#nav')
        assert nav.locator('a[href="#/admin/users"]').count() == 0
        assert nav.locator('a[href="#/surveys"]').count() == 0
        assert nav.locator('a[href="#/suggestions"]').count() == 0
        if staff:
            nav.locator('summary').filter(has_text='상담 정보').click()
            nav.get_by_role('link', name='내 알림', exact=True).click()
            page.wait_for_selector('body[data-ready="/inbox"]', state='attached')
            nav.locator('summary').filter(has_text='예약 관리').click()
            nav.get_by_role('link', name='상담 시간', exact=True).click()
            page.wait_for_selector('body[data-ready="/slots"]', state='attached')
        else:
            assert nav.locator('.nav-group').count() == 0
            nav.get_by_role('link', name='내 예약', exact=True).click()
            page.wait_for_selector('body[data-ready="/my-bookings"]', state='attached')
    finally:
        s.close()


def test_activity_retry_keeps_latest_first_and_pagination(server, browser):  # noqa: F811
    base, _ = server
    s = Session(browser, base, 'prof@test.ac.kr', {'width': 1280, 'height': 900}, service_workers='block')
    page = s.page
    try:
        calls = []
        event = {'booking_id': 7, 'action': 'cancel', 'actor_name': '테스트',
                 'student_name': '학생', 'actor_is_student': True, 'at': '2026-11-17T01:00:00Z',
                 'start_at': '2026-11-18T04:00:00Z', 'status': 'cancelled', 'detail': ''}
        def events(route):
            calls.append(route.request.url)
            if len(calls) == 1:
                route.fulfill(json={})  # malformed response exercises the recoverable error view
            elif 'before_id=' in route.request.url:
                route.fulfill(json={'items': [{**event, 'id': 10}], 'next_before_id': None})
            else:
                route.fulfill(json={'items': [{**event, 'id': 30}, {**event, 'id': 20}], 'next_before_id': 20})
        page.route('**/api/staff/booking-events?*', events)
        s.go('/bookings')
        page.get_by_role('button', name='예약 활동 기록', exact=True).click()
        page.get_by_text('기록을 불러오지 못했습니다.', exact=False).wait_for()
        page.get_by_role('button', name='기록 새로고침').click()
        page.locator('[data-event-id="30"]').wait_for()
        page.get_by_role('button', name='이전 기록 더 보기').click()
        page.locator('[data-event-id="10"]').wait_for()
        ids = page.locator('.activity-table tbody tr').evaluate_all("rows => rows.map(r => r.dataset.eventId)")
        assert ids == ['30', '20', '10']
    finally:
        s.close()
