"""Professor's durable inbox works without browser push registration."""
import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_professor_inbox_read_and_refresh(server, browser, viewport):  # noqa: F811
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    calls = []
    item = {"id": 1, "kind": "created", "title": "새 상담 예약", "body": "예약 관리에서 확인하세요.",
            "url": "#/bookings", "created_on": "2026-11-13", "arrived_at": "2026-11-13T10:02:43+09:00", "read": False}
    def inbox(route):
        calls.append(route.request.method)
        if route.request.method == "PUT":
            item["read"] = True
            route.fulfill(json={"ok": True})
        else:
            route.fulfill(json={"items": [item], "unread": int(not item["read"])})
    prof.page.route("**/api/inbox**", inbox)
    prof.go("/inbox")
    prof.page.get_by_role("heading", name="내 알림", exact=True).wait_for()
    prof.page.get_by_text("읽지 않은 알림 1건", exact=True).wait_for()
    prof.page.get_by_text("알림 시각 2026-11-13 10:02 (한국시간)", exact=True).wait_for()
    prof.page.get_by_role("button", name="읽음 표시", exact=True).click()
    prof.page.get_by_text("읽지 않은 알림 0건", exact=True).wait_for()
    assert calls.count("PUT") == 1
    assert prof.page.locator("body").evaluate("e => e.scrollWidth <= innerWidth")
    prof.page.get_by_role("button", name="알림 새로고침").click()
    assert prof.page.get_by_role("button", name="읽음", exact=True).is_disabled()
    prof.ctx.close()


@pytest.mark.parametrize('email', ['prof@test.ac.kr', 'admin@test.ac.kr'])
@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_header_bell_is_accessible_and_preserves_more(server, browser, viewport, email):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, email, viewport, service_workers='block')
    calls = []
    item = {'id': 1, 'kind': 'created', 'title': '새 상담 예약', 'body': '예약 관리에서 확인하세요.',
            'url': '#/bookings', 'created_on': '2026-11-13', 'arrived_at': '2026-11-13T00:05:59+09:00', 'read': False}
    def inbox(route):
        calls.append(route.request.method)
        if route.request.method == 'PUT':
            item['read'] = True
            route.fulfill(json={'ok': True})
        else:
            route.fulfill(json={'items': [item], 'unread': int(not item['read'])})
    staff.page.route('**/api/inbox**', inbox)
    staff.page.reload()
    bell = staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 1건', exact=True)
    bell.wait_for()
    bell.click()
    panel = staff.page.get_by_role('region', name='알림 모아보기')
    panel.get_by_text('새 상담 예약', exact=True).wait_for()
    panel.get_by_text('알림 시각 2026-11-13 00:05 (한국시간)', exact=True).wait_for()
    panel.get_by_role('button', name='읽음 표시', exact=True).click()
    staff.page.get_by_role('button', name='알림 열기', exact=True).wait_for()
    panel.get_by_role('button', name='닫기', exact=True).focus()
    staff.page.keyboard.press('Escape')
    assert staff.page.locator('#inbox-popover').is_hidden()
    assert staff.page.locator('.inbox-bell').evaluate('e => e === document.activeElement')
    assert staff.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    assert calls.count('PUT') == 1
    if viewport == MOBILE:
        button_box = staff.page.locator('.inbox-bell').bounding_box()
        assert button_box['y'] < 70 and button_box['x'] > viewport['width'] / 2
        staff.page.get_by_role('button', name='더보기 메뉴').click()
        staff.page.locator('#nav').get_by_role('link', name='내 알림', exact=True).wait_for()
    staff.ctx.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_student_has_no_staff_bell_or_inbox_requests(server, browser, viewport):  # noqa: F811
    base, _ = server
    student = Session(browser, base, 'bell-student@example.test', viewport, service_workers='block')
    calls = []
    student.page.on('request', lambda request: calls.append(request.url) if '/api/inbox' in request.url else None)
    student.page.reload()
    student.page.wait_for_selector('body[data-ready="/booking"]')
    assert student.page.locator('.inbox-bell').count() == 0
    assert student.page.locator('#nav a[href="#/inbox"]').count() == 0
    assert calls == []
    student.ctx.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_inbox_can_reach_older_unread_notifications(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, 'prof@test.ac.kr', viewport, service_workers='block')
    def inbox(route):
        older = 'before_id=20' in route.request.url
        nid = 10 if older else 20
        route.fulfill(json={'items': [{'id': nid, 'kind': 'created', 'title': f'가상 알림 {nid}',
            'body': '예약 관리에서 확인하세요.', 'url': '#/bookings', 'created_on': '2026-11-13', 'read': False}],
            'unread': 2, 'has_more': not older, 'next_before_id': None if older else 20})
    staff.page.route('**/api/inbox**', inbox)
    staff.go('/inbox')
    staff.page.get_by_role('heading', name='가상 알림 20', exact=True).wait_for()
    staff.page.get_by_role('button', name='이전 알림 더 보기').click()
    staff.page.get_by_role('heading', name='가상 알림 10', exact=True).wait_for()
    assert staff.page.locator('[data-notification-id]').count() == 2
    assert staff.page.get_by_role('button', name='이전 알림 더 보기').is_hidden()
    staff.page.get_by_role('button', name='미읽음만', exact=True).click()
    assert staff.page.get_by_role('button', name='미읽음만', exact=True).get_attribute('aria-pressed') == 'true'
    assert staff.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    staff.ctx.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
@pytest.mark.parametrize('email', ['prof@test.ac.kr', 'admin@test.ac.kr'])
def test_content_open_marks_read_and_read_all_survives_reload(server, browser, viewport, email):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, email, viewport, service_workers='block')
    items = [{'id': i, 'kind': 'created', 'title': f'가상 알림 {i}', 'body': '가상 내용',
        'url': '#/bookings', 'created_on': '2026-11-13', 'read': False} for i in range(1, 6)]
    writes = []
    def inbox(route):
        if route.request.method == 'PUT':
            writes.append(route.request.url)
            for item in items:
                if route.request.url.endswith('/read-all') or route.request.url.endswith(f"/{item['id']}/read"):
                    item['read'] = True
            route.fulfill(json={'ok': True, 'unread': sum(not x['read'] for x in items)})
        else:
            selected = [x for x in items if not x['read']] if 'unread_only=true' in route.request.url else items
            route.fulfill(json={'items': selected, 'unread': sum(not x['read'] for x in items), 'has_more': False})
    staff.page.route('**/api/inbox**', inbox)
    staff.page.reload()
    staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 5건', exact=True).click()
    panel = staff.page.locator('#inbox-popover')
    panel.get_by_role('link', name='내용 확인').first.click()
    staff.page.wait_for_url('**/#/bookings')
    staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 4건', exact=True).wait_for()
    assert items[0]['read'] and len(writes) == 1
    staff.go('/inbox')
    staff.page.locator('[data-notification-id="2"]').get_by_role('link', name='내용 확인').click()
    staff.page.wait_for_url('**/#/bookings')
    staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 3건', exact=True).wait_for()
    staff.go('/inbox')
    staff.page.get_by_role('button', name='모두 읽음', exact=True).click()
    staff.page.get_by_text('읽지 않은 알림 0건', exact=True).wait_for()
    assert staff.page.locator('.inbox-badge').is_hidden()
    staff.page.reload()
    staff.page.get_by_role('button', name='알림 열기', exact=True).wait_for()
    assert staff.page.locator('.inbox-badge').is_hidden()
    assert staff.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    assert len(writes) == 3
    staff.ctx.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_read_failure_does_not_hide_count_and_focus_refreshes(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, 'prof@test.ac.kr', viewport, service_workers='block')
    item = {'id': 1, 'title': '가상 알림', 'body': '가상 내용', 'url': '#/bookings',
            'created_on': '2026-11-13', 'read': False}
    def inbox(route):
        if route.request.method == 'PUT':
            route.fulfill(status=503, json={'message': '가상 저장 실패'})
        else:
            route.fulfill(json={'items': [item], 'unread': int(not item['read']), 'has_more': False})
    staff.page.route('**/api/inbox**', inbox)
    staff.go('/inbox')
    staff.page.locator('[data-notification-id="1"]').get_by_role('link', name='내용 확인').click()
    staff.page.get_by_text('가상 저장 실패', exact=True).wait_for()
    assert staff.page.url.endswith('#/inbox')
    staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 1건', exact=True).wait_for()
    item['read'] = True  # Simulate a read from another device.
    staff.page.evaluate('window.dispatchEvent(new Event("focus"))')
    staff.page.get_by_text('읽지 않은 알림 0건', exact=True).wait_for()
    assert staff.page.locator('.inbox-badge').is_hidden()
    staff.ctx.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_close_during_read_does_not_navigate_and_storage_refreshes(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, 'prof@test.ac.kr', viewport, service_workers='block')
    item = {'id': 1, 'title': '가상 알림', 'body': '가상 내용', 'url': '#/suggestions',
            'created_on': '2026-11-13', 'read': False}
    pending = []
    def inbox(route):
        if route.request.method == 'PUT':
            pending.append(route)
        else:
            route.fulfill(json={'items': [item], 'unread': int(not item['read']), 'has_more': False})
    staff.page.route('**/api/inbox**', inbox)
    staff.page.reload()
    staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 1건', exact=True).click()
    before = staff.page.url
    panel = staff.page.locator('#inbox-popover')
    with staff.page.expect_request('**/api/inbox/1/read'):
        panel.get_by_role('link', name='내용 확인').click()
    panel.get_by_role('button', name='닫기', exact=True).click()
    assert len(pending) == 1
    item['read'] = True
    pending[0].fulfill(json={'ok': True, 'unread': 0})
    staff.page.get_by_role('button', name='알림 열기', exact=True).wait_for()
    assert staff.page.url == before
    assert panel.is_hidden()
    item['read'] = False
    staff.page.evaluate('window.dispatchEvent(new StorageEvent("storage", {key: "inbox-refresh"}))')
    staff.page.get_by_role('button', name='알림 열기, 읽지 않은 알림 1건', exact=True).wait_for()
    staff.ctx.close()
