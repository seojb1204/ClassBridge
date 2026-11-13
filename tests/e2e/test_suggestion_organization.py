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


@pytest.mark.parametrize('viewport', [PC, MOBILE])
@pytest.mark.parametrize('email', ['prof@test.ac.kr', 'admin@test.ac.kr'])
def test_trash_yes_no_and_empty_all_ignore_filters(server, browser, viewport, email):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, email, viewport, service_workers='block')
    rows = [{'id': f'trash-{i}', 'category': 'other', 'content': f'가상 휴지통 {i}',
             'submitted_on': '2026-11-13', 'status': 'new', 'is_public': False,
             'deleted_on': '2026-11-13', 'replies': []} for i in range(3)]
    writes = []
    def handle(route):
        url = route.request.url
        if url.endswith('/stats'):
            route.fulfill(json={'total': 0, 'by_status': {}, 'by_category': {}})
        elif url.endswith('/trash/preview'):
            route.fulfill(json={'ids': [r['id'] for r in rows], 'count': len(rows)})
        elif url.endswith('/trash/empty'):
            writes.append(route.request)
            count = len(rows)
            rows.clear()
            route.fulfill(json={'deleted': count})
        elif url.endswith('/purge'):
            writes.append(route.request)
            rows[:] = [r for r in rows if f"/{r['id']}/purge" not in url]
            route.fulfill(status=204)
        else:
            # Current page/filter displays one row, but bulk scope is full trash.
            route.fulfill(json=rows[:1] if 'trash=true' in url or url.endswith('/search') else [])
    staff.page.route('**/api/suggestions**', handle)
    staff.go('/suggestions')
    staff.page.get_by_role('button', name='휴지통', exact=True).click()
    staff.page.get_by_role('button', name='영구 삭제', exact=True).click()
    dialog = staff.page.get_by_role('dialog')
    assert dialog.locator('input').count() == 0
    dialog.get_by_role('button', name='아니요', exact=True).click()
    assert writes == []
    staff.page.get_by_role('button', name='영구 삭제', exact=True).click()
    dialog.get_by_role('button', name='예, 영구 삭제', exact=True).click()
    staff.page.get_by_text('가상 휴지통 1', exact=True).wait_for()
    assert len(writes) == 1 and writes[0].post_data_json == {'confirmation': '영구 삭제'}
    staff.page.get_by_role('button', name='휴지통 비우기', exact=True).click()
    dialog.get_by_text('현재 휴지통 전체 2건', exact=False).wait_for()
    staff.page.keyboard.press('Escape')
    assert len(writes) == 1
    staff.page.get_by_role('button', name='휴지통 비우기', exact=True).click()
    dialog.get_by_role('button', name='예, 영구 삭제', exact=True).click()
    staff.page.get_by_text('휴지통이 비어 있습니다.', exact=True).wait_for()
    assert len(writes) == 2
    assert writes[-1].post_data_json == {'confirmation': '영구 삭제', 'ids': ['trash-1', 'trash-2']}
    assert staff.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    staff.ctx.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
@pytest.mark.parametrize('email', ['prof@test.ac.kr', 'admin@test.ac.kr'])
def test_trash_select_all_except_one_and_cancel(server, browser, viewport, email):  # noqa: F811
    base, _ = server
    staff = Session(browser, base, email, viewport, service_workers='block')
    rows = [{'id': f'select-{i}', 'category': 'other', 'content': f'가상 선택 건의 {i}',
             'submitted_on': '2026-11-13', 'status': 'new', 'is_public': False,
             'deleted_on': '2026-11-13', 'replies': []} for i in range(3)]
    writes = []
    def handle(route):
        url = route.request.url
        if url.endswith('/stats'):
            route.fulfill(json={'total': 0, 'by_status': {}, 'by_category': {}})
        elif url.endswith('/trash/delete-selected'):
            body = route.request.post_data_json
            writes.append(body)
            rows[:] = [r for r in rows if r['id'] not in body['ids']]
            route.fulfill(json={'deleted': len(body['ids'])})
        else:
            route.fulfill(json=rows if 'trash=true' in url else [])
    staff.page.route('**/api/suggestions**', handle)
    staff.go('/suggestions')
    staff.page.get_by_role('button', name='휴지통', exact=True).click()
    all_box = staff.page.get_by_role('checkbox', name='현재 페이지 전체 선택', exact=True)
    all_box.wait_for()
    delete = staff.page.get_by_role('button', name='선택 삭제', exact=True)
    assert delete.is_disabled()
    all_box.check()
    staff.page.get_by_role('checkbox', name='건의 선택: 가상 선택 건의 1', exact=True).uncheck()
    staff.page.get_by_text('2건 선택 / 현재 페이지 3건', exact=True).wait_for()
    assert all_box.evaluate('el => el.indeterminate')
    staff.shot(f'trash_selection_{email.split("@")[0]}_{viewport["width"]}')
    delete.click()
    dialog = staff.page.get_by_role('dialog', name='선택한 건의 영구 삭제', exact=True)
    assert dialog.get_by_text('선택한 2건', exact=False).is_visible()
    dialog.get_by_role('button', name='아니요', exact=True).click()
    assert not writes
    assert staff.page.get_by_role('checkbox', name='건의 선택: 가상 선택 건의 0', exact=True).is_checked()
    delete.click()
    dialog.get_by_role('button', name='예, 영구 삭제', exact=True).click()
    staff.page.get_by_text('0건 선택 / 현재 페이지 1건', exact=True).wait_for()
    assert writes == [{'confirmation': '영구 삭제', 'ids': ['select-0', 'select-2']}]
    assert staff.page.get_by_text('가상 선택 건의 1', exact=True).is_visible()
    assert delete.is_disabled()
    all_box.check()
    staff.page.get_by_label('건의 정렬', exact=True).select_option('oldest')
    staff.page.get_by_text('0건 선택 / 현재 페이지 1건', exact=True).wait_for()
    assert not all_box.is_checked()
    assert staff.page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    staff.close()
