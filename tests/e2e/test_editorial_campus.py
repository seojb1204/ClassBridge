"""Selected C design: local fixture accounts only, no production side effects."""
import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('viewport', [PC, MOBILE, {'width': 768, 'height': 1024}])
@pytest.mark.parametrize('email,routes', [
    ('prof@test.ac.kr', ['/slots', '/bookings', '/surveys', '/suggestions', '/inbox']),
    ('admin@test.ac.kr', ['/slots', '/admin/users', '/admin/settings', '/admin/audit']),
    ('design-student@test.ac.kr', ['/booking', '/my-bookings', '/surveys']),
])
def test_editorial_all_roles_layout(server, browser, viewport, email, routes):  # noqa: F811
    base, _ = server
    s = Session(browser, base, email, viewport, service_workers='block')
    for route in routes:
        s.go(route)
        page = s.page
        assert page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
        assert page.locator('.brand').inner_text() == 'ClassBridge'
        assert page.locator('body').evaluate('e => getComputedStyle(e).backgroundColor') == 'rgb(247, 243, 236)'
        assert page.locator('#view h1').count() >= 1
        if viewport['width'] == 390:
            assert page.locator('#mobile-tabs').is_visible()
        s.shot(f'editorial_{email.split("@")[0]}_{route.replace("/", "_")}_{viewport["width"]}')
    # A skip link must not change the SPA route or erase the screen.
    before = s.page.url
    s.page.locator('.skip-link').focus()
    s.page.keyboard.press('Enter')
    assert s.page.url == before
    assert s.page.locator('#view').evaluate('e => e === document.activeElement')
    s.close()
