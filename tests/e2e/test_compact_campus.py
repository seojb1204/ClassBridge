"""Compact support panels: local mocked data only, shared campus palette."""
import os
from datetime import timedelta

import pytest

from app.db import utcnow
from app.timeutil import today_kst
from tests.e2e.test_e2e import Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('width', [360, 390, 1366])
@pytest.mark.parametrize('email,path', [('compact-student@test.ac.kr', '/booking'),
                                        ('prof@test.ac.kr', '/slots')])
def test_compact_support_panels(server, browser, width, email, path):  # noqa: F811
    base, _ = server
    s = Session(browser, base, email, {'width': width, 'height': 900}, service_workers='block')
    page = s.page
    days = [(today_kst(utcnow()) + timedelta(days=i)).isoformat() for i in range(1, 6)]
    page.route('**/api/slots/available-days', lambda r: r.fulfill(
        json=[{'date': day, 'count': 2} for day in days]))
    page.route('**/api/announcement', lambda r: r.fulfill(json={'announcement': {
        'title': '상담 전 준비 안내', 'body': '긴 공지 내용도 생략 없이 다시 펼쳐 읽을 수 있습니다.\n' * 12,
        'published': True, 'revision': 1}}))
    page.reload()
    s.go(path)
    support = page.locator('.calendar-support')
    if support.count() and not support.evaluate('e => e.open'):
        support.locator(':scope > summary').click()
    notice = page.locator('.announcement-panel')
    notice.wait_for()
    if page.locator('.other-available-days').count():
        page.locator('.other-available-days > summary').click()
    availability = page.locator('.available-days')
    body = notice.locator('.announcement-body')
    if email.startswith('compact-student'):
        assert not notice.evaluate('e => e.open')
        assert notice.get_by_text('새 공지').is_visible()
        notice.locator('summary').click()
        assert not notice.get_by_text('새 공지').is_visible()
    assert body.bounding_box()['height'] > 100
    notice.locator('summary').click()
    assert not body.is_visible()
    s.shot(f'compact_support_{email.split("@")[0]}_{width}')
    notice.locator('summary').click()
    assert body.bounding_box()['height'] > 100
    buttons = availability.locator('.available-day-buttons button')
    assert buttons.count() == 3
    assert availability.bounding_box()['height'] < 170
    for button in buttons.all():
        assert button.bounding_box()['height'] >= 44
    availability.get_by_role('button', name='전체 일정 보기').click()
    assert buttons.count() == 5
    availability.get_by_role('button', name='가까운 일정만 보기').click()
    assert buttons.count() == 3
    assert page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    s.close()
