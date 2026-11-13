"""Readability checks use isolated fake sessions, never production data."""
import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, SHOTS, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_guest_writer_keeps_privacy_visible_and_limits_width(server, browser, viewport):  # noqa: F811
    base, _ = server
    ctx = browser.new_context(viewport=viewport, locale="ko-KR")
    page = ctx.new_page()
    page.goto(base)
    page.locator('.login-box').wait_for()
    assert page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    page.screenshot(path=str(SHOTS / f'polish_login_{viewport["width"]}.png'), full_page=True)
    page.get_by_role('link', name='로그인 없이 익명 건의하기').click()
    writer = page.get_by_role('region', name='익명 건의 작성')
    writer.wait_for()
    assert writer.bounding_box()['width'] <= 740
    assert page.locator('.privacy-summary').is_visible()
    assert '작성자가 추측될 수 있습니다' in page.locator('.privacy-summary').inner_text()
    assert page.get_by_label('공개 범위').input_value() == 'private'
    detail = page.locator('.help-details')
    assert detail.get_attribute('open') is None
    detail.locator('summary').click()
    assert detail.get_attribute('open') is not None
    assert detail.get_by_text('새 건의 접수 즉시', exact=False).is_visible()
    detail.locator('summary').click()
    assert page.locator('.privacy-summary').is_visible()
    page.get_by_label('내용', exact=True).fill('가상 화면 점검 내용')
    assert page.locator('.writer-actions small').inner_text() == f'{len("가상 화면 점검 내용")} / 2000'
    assert page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    page.screenshot(path=str(SHOTS / f'polish_writer_{viewport["width"]}.png'), full_page=True)
    ctx.close()  # Do not submit even to the test server in this visual pass.


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_inbox_read_state_and_disclosure(server, browser, viewport):  # noqa: F811
    base, _ = server
    s = Session(browser, base, 'prof@test.ac.kr', viewport, service_workers='block')
    item = {'id': 1, 'kind': 'created', 'title': '새 상담 예약', 'body': '예약 관리에서 확인하세요.',
            'url': '#/bookings', 'arrived_at': '2026-11-13T10:02:43+09:00', 'read': False}

    def inbox(route):
        if route.request.method == 'PUT':
            item['read'] = True
            route.fulfill(json={'ok': True})
        else:
            route.fulfill(json={'items': [item], 'unread': int(not item['read'])})

    s.page.route('**/api/inbox**', inbox)
    s.go('/inbox')
    card = s.page.locator('.inbox-item')
    card.locator('.inbox-read-state').get_by_text('읽지 않음', exact=True).wait_for()
    assert 'is-unread' in card.get_attribute('class')
    assert s.page.locator('.inbox-bell svg').count() == 1
    details = s.page.locator('.help-details')
    details.locator('summary').click()
    assert details.get_by_text('실제 휴대폰 수신 시각이 아닙니다.', exact=False).is_visible()
    details.locator('summary').click()
    s.shot(f'polish_inbox_unread_{viewport["width"]}')
    card.get_by_role('button', name='읽음 표시', exact=True).click()
    card.locator('.inbox-read-state').get_by_text('읽음', exact=True).wait_for()
    assert 'is-read' in card.get_attribute('class')
    assert s.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    s.shot(f'polish_inbox_read_{viewport["width"]}')
    s.close()
