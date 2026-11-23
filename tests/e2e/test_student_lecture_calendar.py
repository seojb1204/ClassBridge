import os

import httpx
import pytest

from tests.conftest import future_day
from tests.e2e.test_e2e import MOBILE, PC, Session, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('viewport', [MOBILE, PC])
def test_student_real_lectures_and_consultation_priority(server, browser, viewport):  # noqa: F811
    base, _ = server
    day = future_day(2 if viewport == MOBILE else 9).isoformat()
    with httpx.Client(base_url=base) as staff:
        assert staff.post('/auth/dev/login', json={'email': 'prof@test.ac.kr'}).status_code == 200
        staff.headers['X-CSRF-Token'] = staff.get('/api/me').json()['csrf_token']
        for start, end in [('10:00', '12:00'), ('14:00', '17:00')]:
            assert staff.post('/api/lectures', json={'title': '조회 전용 강의', 'location': '101',
                'date': day, 'start_time': start, 'end_time': end}).status_code == 201
        r = staff.post('/api/slots', json={'start_date': day, 'start_time': '16:20', 'end_time': '16:40',
            'duration_minutes': 20, 'kind': 'individual', 'capacity': 1})
        assert r.status_code == 201, r.text
        slot_id = r.json()['slot_ids'][0]
    student = Session(browser, base, f'lecture-read-{viewport["width"]}@test.ac.kr', viewport, service_workers='block')
    p = student.page
    try:
        student.go('/booking')
        if viewport == MOBILE:
            p.get_by_role('button', name='달력형', exact=True).click()
        # Navigate to the created week if another viewport's earlier slot is selected first.
        if not p.locator(f'[data-event-type="consultation"][data-slot-id="{slot_id}"]').count():
            p.get_by_role('button', name='다음 주', exact=True).click()
        p.locator(f'[data-event-type="consultation"][data-slot-id="{slot_id}"]').wait_for()
        lecture = p.locator('[data-event-type="lecture"]').first
        lecture.click()
        dialog = p.get_by_role('dialog', name='강의 시간', exact=True)
        assert dialog.get_by_role('button').count() == 1
        assert dialog.get_by_role('button', name='닫기').is_visible()
        p.go_back()
        dialog.wait_for(state='detached')
        consultation = p.locator(f'[data-event-type="consultation"][data-slot-id="{slot_id}"]')
        cb = consultation.bounding_box()
        for event in p.locator('[data-event-type="lecture"]').all():
            lb = event.bounding_box()
            assert lb['y'] + lb['height'] <= cb['y'] + 1 or cb['y'] + cb['height'] <= lb['y'] + 1
        consultation.click()
        p.get_by_role('dialog', name='상담 예약', exact=True).wait_for()
        assert p.get_by_role('button', name='예약하기', exact=True).is_visible()
        p.go_back()
        p.locator('.modal').wait_for(state='detached')
        student.shot('student_lecture_calendar_' + str(viewport['width']))
    finally:
        student.close()


@pytest.mark.parametrize('viewport', [MOBILE, PC])
def test_error_toast_dismisses_immediately(server, browser, viewport):  # noqa: F811
    base, _ = server
    student = Session(browser, base, f'toast-{viewport["width"]}@test.ac.kr', viewport, service_workers='block')
    p = student.page
    try:
        p.evaluate('''async () => {
          const {toast}=await import('/static/js/ui.js');
          toast('마감','error'); toast('다른 알림','info');
        }''')
        alert = p.get_by_role('alert').filter(has_text='마감')
        alert.click()
        assert alert.count() == 0
        assert p.get_by_role('status').filter(has_text='다른 알림').is_visible()
        p.get_by_role('status').filter(has_text='다른 알림').focus()
        p.keyboard.press('Enter')
        assert p.locator('.toast').count() == 0
    finally:
        student.close()
