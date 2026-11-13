"""User-flow regressions with isolated synthetic data only."""
import os

import pytest

from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E 미설정')


@pytest.mark.parametrize('viewport', [PC, MOBILE])
@pytest.mark.parametrize('email', ['prof@test.ac.kr', 'admin@test.ac.kr'])
def test_survey_delete_yes_no_escape_navigation_and_retry(server, browser, viewport, email):  # noqa: F811
    base, _ = server
    user = Session(browser, base, email, viewport, service_workers='block')
    page = user.page
    row = {'id': 909090, 'title': '가상 삭제 UX 설문', 'status': 'closed', 'response_count': 3}
    writes = []

    def handle(route):
        if route.request.method == 'POST':
            writes.append(route.request.post_data_json)
            if len(writes) == 1:
                row['response_count'] = 4
                route.fulfill(status=409, json={'message': '응답 수가 변경되었습니다. 다시 확인해 주세요.'})
            else:
                route.fulfill(status=204)
        else:
            route.fulfill(json=[row] if len(writes) < 2 else [])

    page.route('**/api/surveys**', handle)
    user.go('/surveys')
    page.get_by_role('button', name='휴지통', exact=True).click()
    for dismiss in ['아니오', 'Escape', 'navigate']:
        page.get_by_role('button', name='영구 삭제', exact=True).click()
        dialog = page.get_by_role('dialog')
        assert dialog.locator('input').count() == 0
        assert '답변 3건' in dialog.inner_text()
        assert '복원할 수 없습니다' in dialog.inner_text()
        assert dialog.get_by_role('button', name='아니오').evaluate('e => e === document.activeElement')
        if dismiss == 'Escape':
            page.keyboard.press('Escape')
        elif dismiss == 'navigate':
            page.evaluate("location.hash = '#/inbox'")
        else:
            dialog.get_by_role('button', name=dismiss).click()
        dialog.wait_for(state='hidden')
        assert not writes
        if dismiss == 'navigate':
            user.go('/surveys')
    page.get_by_role('button', name='영구 삭제', exact=True).click()
    page.get_by_role('button', name='예, 영구 삭제').click()
    page.get_by_role('alert').filter(has_text='응답 수가 변경').wait_for()
    assert writes == [{'confirmation': '영구 삭제', 'response_count': 3}]
    page.get_by_text('응답 4건', exact=True).wait_for()
    page.get_by_role('button', name='영구 삭제', exact=True).click()
    assert '답변 4건' in page.get_by_role('dialog').inner_text()
    page.get_by_role('button', name='예, 영구 삭제').click()
    page.get_by_text('휴지통이 비어 있습니다.', exact=True).wait_for()
    assert len(writes) == 2
    assert page.locator('body').evaluate('e => e.scrollWidth <= innerWidth')
    user.shot('survey_delete_ux_' + email.split('@')[0] + '_' + str(viewport['width']))
    user.close()


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_survey_required_summary_labels_optional_clear(server, browser, viewport):  # noqa: F811
    base, _ = server
    user = Session(browser, base, 'survey-ux@test.ac.kr', viewport, service_workers='block')
    page = user.page
    survey = {'id': 909091, 'title': '가상 응답 UX 설문', 'is_open': True, 'participated': False,
              'questions': [
                  {'id': 1, 'title': '필수 한줄', 'qtype': 'short', 'required': True},
                  {'id': 2, 'title': '필수 여러줄', 'qtype': 'long', 'required': True},
                  {'id': 3, 'title': '필수 목록', 'qtype': 'dropdown', 'required': True, 'options': ['가', '나']},
                  {'id': 4, 'title': '선택 단일', 'qtype': 'single', 'required': False, 'options': ['가', '나']},
                  {'id': 5, 'title': '선택 척도', 'qtype': 'scale5', 'required': False},
                  {'id': 6, 'title': '필수 복수', 'qtype': 'multi', 'required': True, 'options': ['가', '나']},
              ]}
    writes = []
    page.route('**/api/surveys/student/909091', lambda route: route.fulfill(json=survey))

    def submit(route):
        writes.append(route.request.post_data_json)
        route.fulfill(json={'message': '가상 제출 완료'})

    page.route('**/api/surveys/909091/responses', submit)
    user.go('/surveys/take/909091')
    page.get_by_role('button', name='제출', exact=True).click()
    assert not writes
    summary = page.locator('.survey-form > .error-box')
    assert summary.evaluate('e => e === document.activeElement')
    assert '필수 문항 4개' in summary.inner_text()
    summary.get_by_role('button', name='필수 한줄').click()
    assert page.get_by_role('textbox', name='필수 한줄').evaluate('e => e === document.activeElement')
    page.get_by_role('textbox', name='필수 한줄').fill('답변 보존')
    page.get_by_role('textbox', name='필수 여러줄').fill('여러줄 답변')
    page.get_by_role('combobox', name='필수 목록').select_option('가')
    page.get_by_role('group', name='필수 복수').get_by_label('가', exact=True).check()
    for title in ['선택 단일', '선택 척도']:
        group = page.get_by_role('group', name=title)
        group.get_by_role('radio').first.check()
        group.get_by_role('button', name='선택 해제').click()
        assert group.locator('input:checked').count() == 0
    user.shot('survey_response_ux_' + str(viewport['width']))
    page.get_by_role('button', name='제출', exact=True).click()
    page.get_by_text('응답이 익명으로 제출되었습니다. 감사합니다.', exact=True).wait_for()
    assert writes[0]['answers'] == {'1': '답변 보존', '2': '여러줄 답변', '3': '가', '4': None, '5': None, '6': ['가']}
    user.close()


def test_survey_latest_tab_wins(server, browser):  # noqa: F811
    base, _ = server
    user = Session(browser, base, 'prof@test.ac.kr', PC, service_workers='block')
    page = user.page
    held = []
    row = {'id': 909092, 'title': '최신 설문 목록', 'status': 'draft', 'response_count': 0}

    def handle(route):
        if route.request.url.endswith('trash=true'):
            held.append(route)
        else:
            route.fulfill(json=[row])

    page.route('**/api/surveys?*', handle)
    user.go('/surveys')
    # The module can retain the previous trash state; select the active list first.
    page.get_by_role('button', name='설문 목록', exact=True).click()
    with page.expect_request('**/api/surveys?trash=true'):
        page.get_by_role('button', name='휴지통', exact=True).click()
    with page.expect_response('**/api/surveys?trash=false'):
        page.get_by_role('button', name='설문 목록', exact=True).click()
    with page.expect_response('**/api/surveys?trash=true'):
        held[-1].fulfill(json=[{**row, 'title': '오래된 휴지통 응답'}])
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    assert page.get_by_text('오래된 휴지통 응답', exact=True).count() == 0
    assert page.get_by_role('button', name='설문 목록', exact=True).get_attribute('aria-pressed') == 'true'
    user.close()
