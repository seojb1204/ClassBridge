"""Consultation registration keeps native calendar selection and sentence input in sync."""
import os

import pytest
from playwright.sync_api import expect

from tests.e2e.test_e2e import Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('width', [360, 390, 1280])
def test_registration_calendar_and_sentence_sync(server, browser, width):  # noqa: F811
    base, _ = server
    s = Session(browser, base, 'prof@test.ac.kr', {'width': width, 'height': 900}, service_workers='block')
    p = s.page
    try:
        s.go('/slots/new')
        date = p.get_by_label('날짜(시작일)', exact=True)
        expect(date).to_have_attribute('type', 'date')
        date.fill('2027-01-04')
        date.dispatch_event('change')
        expect(p.locator('.notice').first).to_contain_text('2027-01-04')
        # A calendar selection never submits or writes data until explicit preview/confirmation.
        calls = []
        p.on('request', lambda req: calls.append(req.url) if req.method == 'POST' else None)
        date.evaluate('e => { e.showPicker = () => { window.pickerCalls = (window.pickerCalls || 0) + 1; }; }')
        date.click()
        assert p.evaluate('window.pickerCalls') == 1
        p.get_by_placeholder('예: 내일 오후 두시~네시반 30분씩').fill('2027-01-05 오전 10시~12시 30분씩')
        p.get_by_role('button', name='입력 내용 적용').click()
        expect(date).to_have_value('2027-01-05')
        assert calls == []
        assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # Unsupported/restricted showPicker must not make the date field unusable.
        date.evaluate('e => { e.showPicker = () => { throw new DOMException("restricted"); }; }')
        date.click()
        date.fill('2027-01-06')
        date.dispatch_event('change')
        expect(p.locator('.notice').first).to_contain_text('2027-01-06')
        p.get_by_role('button', name='강의', exact=True).click()
        expect(p.get_by_label('날짜', exact=True)).to_have_attribute('type', 'date')
        p.get_by_role('button', name='상담 시간', exact=True).click()
        expect(date).to_have_value('2027-01-06')
        s.shot(f'registration_date_calendar_{width}')
    finally:
        s.close()
