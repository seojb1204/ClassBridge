"""Student changes and private anonymous receipts across desktop/mobile layouts."""
import os

import pytest
from playwright.sync_api import expect

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('viewport', [MOBILE, PC])
def test_private_receipt_roundtrip(server, browser, viewport):  # noqa: F811
    base, _ = server
    context = browser.new_context(viewport=viewport)
    p = context.new_page()
    try:
        p.goto(base + '/static/suggest.html')
        p.get_by_label('내용', exact=True).fill('비공개 답변 경로 확인')
        p.get_by_role('button', name='익명으로 제출').click()
        expect(p.get_by_role('heading', name='건의가 접수되었습니다')).to_be_visible()
        url = p.get_by_label('내 건의 확인 링크').input_value()
        assert '#receipt=' in url
        p.get_by_role('link', name='내 건의 확인', exact=True).click()
        expect(p.get_by_role('heading', name='내 건의 확인')).to_be_visible()
        expect(p.get_by_text('비공개 답변 경로 확인', exact=True)).to_be_visible()
        p.reload()
        expect(p.get_by_text('처리 상태: 접수', exact=True)).to_be_visible()
        assert p.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()


@pytest.mark.parametrize('viewport', [MOBILE, PC])
def test_student_change_read_ack_and_staff_menu(server, browser, viewport):  # noqa: F811
    base, _ = server
    student = Session(browser, base, 'updates-ui@test.ac.kr', viewport, service_workers='block')
    p = student.page
    row = {'id': 777, 'status': 'cancelled', 'cancel_reason': '일정 변경', 'topic': '',
           'latest_update_id': 9, 'unread_update': True, 'consultation_type': 'other',
           'slot': {'start_at': '2026-11-20T10:00:00+09:00', 'kind': 'individual', 'location': '상담실'}}
    def read(route):
        row['unread_update'] = False
        route.fulfill(status=204)
    p.route('**/api/bookings/mine', lambda r: r.fulfill(json=[row]))
    p.route('**/api/bookings/777/updates', lambda r: r.fulfill(json=[
        {'id': 9, 'action': 'cancel_by_staff', 'at': '2026-11-18T10:00:00+09:00', 'detail': '일정 변경'}]))
    p.route('**/api/bookings/777/updates/9/read', read)
    student.go('/my-bookings')
    expect(p.get_by_text('취소됨 · 미확인', exact=True)).to_be_visible()
    p.get_by_role('button', name='변경 내용 확인').click()
    p.get_by_role('button', name='나중에 확인').click()
    expect(p.get_by_text('취소됨 · 미확인', exact=True)).to_be_visible()
    p.get_by_role('button', name='변경 내용 확인').click()
    p.get_by_role('button', name='확인했어요').click()
    expect(p.get_by_text('취소됨 · 미확인', exact=True)).to_have_count(0)
    expect(p.locator('.card.booking.cancelled')).to_be_visible()
    student.close()
    staff = Session(browser, base, 'prof@test.ac.kr', viewport, service_workers='block')
    staff.go('/bookings')
    expect(staff.page.get_by_role('button', name='예약 목록', exact=True)).to_have_attribute('aria-pressed', 'true')
    assert staff.page.locator('#mobile-tabs a[href="#/slots/new"]').count() == 0
    assert staff.page.locator('#mobile-tabs a[href="#/inbox"]').count() == 1
    staff.page.locator('#view').get_by_role('link', name='시간표', exact=True).click()
    expect(staff.page.get_by_role('link', name='+ 일정 등록', exact=True)).to_be_visible()
    staff.close()
