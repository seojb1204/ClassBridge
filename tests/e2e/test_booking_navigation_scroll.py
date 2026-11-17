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
    staff.go("/bookings")
    p.locator('.week-nav').wait_for()
    p.wait_for_load_state('networkidle')
    for name in ['다음 주', '이전 주', '다음 주', '이번 주로 이동']:
        p.evaluate("window.scrollTo(0, 240)")
        p.wait_for_timeout(100)
        before = p.evaluate('scrollY')
        assert before > 100
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
