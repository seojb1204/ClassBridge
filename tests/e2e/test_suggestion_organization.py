import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_suggestion_search_sort_and_safe_details(server, browser, viewport):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, 'prof@test.ac.kr', viewport, service_workers='block')
    content = 'Synthetic searchable opinion ' + 'long text ' * 30
    item = {'id': 'mock-only', 'category': 'other', 'content': content, 'submitted_on': '2026-11-13',
            'status': 'reviewed', 'is_public': False, 'deleted_on': None, 'replies': []}
    requests = []
    def handle(route):
        requests.append(route.request)
        if '/stats' in route.request.url:
            route.fulfill(json={'total': 1, 'by_status': {'reviewed': 1}, 'by_category': {'other': 1}})
        else:
            route.fulfill(json=[item])
    staff.page.route('**/api/suggestions**', handle)
    staff.go('/suggestions')
    staff.page.get_by_label('건의 내용 검색', exact=True).fill('searchable')
    staff.page.get_by_role('button', name='검색', exact=True).click()
    staff.page.get_by_text('건의 내용 전체 보기', exact=True).wait_for()
    assert any(r.method == 'POST' and r.url.endswith('/search') and r.post_data_json['query'] == 'searchable'
               for r in requests)
    assert all('searchable' not in r.url for r in requests)
    staff.page.get_by_text('건의 내용 전체 보기', exact=True).click()
    staff.page.get_by_text(content, exact=True).wait_for()
    assert staff.page.get_by_text('비공개', exact=True).is_visible()
    assert staff.page.get_by_text('내부 메모 없음', exact=True).is_visible()
    with staff.page.expect_response('**/api/suggestions/search'):
        staff.page.get_by_label('건의 정렬', exact=True).select_option('oldest')
    assert any(r.method == 'POST' and r.url.endswith('/search') and r.post_data_json['order'] == 'oldest'
               for r in requests)
    assert staff.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    staff.ctx.close()


def test_late_suggestion_filter_cannot_replace_latest_results(server, browser):  # noqa: F811
    from urllib.parse import parse_qs, urlparse

    base, _ = server
    staff = Session(browser, base, 'prof@test.ac.kr', PC, service_workers='block')
    held = []
    def item(content):
        return {'id': content, 'category': 'other', 'content': content, 'submitted_on': '2026-11-13',
                'status': 'new', 'is_public': False, 'deleted_on': None, 'replies': []}
    def handle(route):
        if '/stats' in route.request.url:
            route.fulfill(json={'total': 1, 'by_status': {'new': 1}, 'by_category': {'other': 1}})
        elif parse_qs(urlparse(route.request.url).query).get('category') == ['lecture']:
            held.append(route)
        else:
            route.fulfill(json=[item('LATEST FILTER RESULT')])
    staff.page.route('**/api/suggestions**', handle)
    staff.go('/suggestions')
    with staff.page.expect_request('**/api/suggestions?*category=lecture*'):
        staff.page.get_by_label('건의 유형', exact=True).select_option('lecture')
    with staff.page.expect_response('**/api/suggestions?*category=other*'):
        staff.page.get_by_label('건의 유형', exact=True).select_option('other')
    staff.page.get_by_text('LATEST FILTER RESULT', exact=True).wait_for()
    assert held
    with staff.page.expect_response('**/api/suggestions?*category=lecture*'):
        held[0].fulfill(json=[item('STALE FILTER RESULT')])
    staff.page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    assert staff.page.get_by_text('STALE FILTER RESULT', exact=True).count() == 0
    assert staff.page.get_by_label('건의 유형', exact=True).input_value() == 'other'
    staff.ctx.close()
