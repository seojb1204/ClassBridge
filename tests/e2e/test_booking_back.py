"""Back dismisses the booking sheet without leaving the selected calendar."""
import os

import pytest

from tests.conftest import future_day
from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('viewport', [MOBILE, PC])
def test_booking_back_close_reopen_and_explicit_close(server, browser, viewport):  # noqa: F811
    base, _ = server
    student = Session(browser, base, f'back-{viewport["width"]}@test.ac.kr', viewport, service_workers='block')
    p = student.page
    day = future_day().isoformat()
    slot = dict(id=99283, start_at=f'{day}T16:20:00+09:00', end_at=f'{day}T16:40:00+09:00',
                kind='individual', capacity=1, remaining=1, status='open', bookable=True,
                mine=False, location='', note='', reason='')
    p.route('**/api/slots?*', lambda r: r.fulfill(json=[slot]))
    student.go('/my-bookings')
    student.go('/booking')
    url = p.url
    card = p.locator('[data-slot-id="99283"]')
    try:
        for close_kind in ('back', 'button', 'escape', 'back'):
            card.click()
            p.locator('.modal textarea').fill('닫기 검사')
            if close_kind == 'back':
                p.go_back()
            elif close_kind == 'button':
                p.locator('.modal').get_by_role('button', name='닫기', exact=True).click()
            else:
                p.keyboard.press('Escape')
            p.locator('.modal').wait_for(state='detached')
            assert p.url == url
            assert card.is_visible()
        student.shot('booking_back_' + str(viewport['width']))
        p.go_back()
        p.wait_for_url('**/#/my-bookings')
        assert p.locator('.modal').count() == 0
    finally:
        student.close()


def test_back_during_submit_and_failed_submit(server, browser):  # noqa: F811
    base, _ = server
    student = Session(browser, base, 'back-pending@test.ac.kr', MOBILE, service_workers='block')
    p = student.page
    try:
        student.go('/my-bookings')
        url = p.url
        p.evaluate('''async () => {
          const {modal,h}=await import('/static/js/ui.js');
          window.submitCount=0;
          window.dialogResult='waiting';
          modal('제출 검사',h('p',{},'검사'),[{label:'저장',handler:()=>{
            window.submitCount++;
            return new Promise(resolve=>window.finishSubmit=resolve);
          }}],{closeOnBack:true}).then(value=>window.dialogResult=value);
        }''')
        p.get_by_role('button', name='저장', exact=True).click()
        p.go_back()
        p.wait_for_function('history.state?.classbridgeModal')
        assert p.locator('.modal').is_visible()
        assert p.get_by_role('button', name='저장', exact=True).is_disabled()
        p.evaluate('finishSubmit(false)')
        p.get_by_role('button', name='저장', exact=True).click()
        assert p.evaluate('submitCount') == 2
        p.evaluate('finishSubmit(true)')
        p.locator('.modal').wait_for(state='detached')
        assert p.url == url
        assert p.evaluate('dialogResult') is True
    finally:
        student.close()
