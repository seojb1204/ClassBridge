"""Only consultations occupy overlapping time; lecture detail retains original bounds."""
import os

import pytest

from tests.e2e.test_e2e import SHOTS, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('width', [1280, 390])
@pytest.mark.parametrize('short', [False, True])
def test_consultation_hides_only_overlapping_lecture_time(server, browser, width, short):  # noqa: F811
    base, _ = server
    page = browser.new_page(viewport={'width': width, 'height': 900})
    try:
        page.goto(base + '/static/offline.html')
        page.add_style_tag(url=base + '/static/css/app.css')
        page.evaluate('''async short => {
            const {renderCalendar} = await import('/static/js/components/week-calendar.js');
            const root = document.createElement('main'); root.className='view';
            document.body.replaceChildren(root);
            const event=(id,start,end,lecture=false)=>({id,start_at:`2026-11-16T${start}:00+09:00`,
                end_at:`2026-11-16T${end}:00+09:00`,status:'open',kind:'individual',capacity:1,
                remaining:1,bookable:true,...(lecture?{event_type:'lecture',title:'원본 강의'}:{})});
            window.originalLecture=event(101,short?'11:55':'11:00',short?'13:05':'15:00',true);
            const slots=[window.originalLecture,event(102,'12:15','12:45',true),event(201,'12:00','13:00')];
            const options={weekStart:'2026-11-16',selectedDay:'2026-11-16',slots,mobileView:'week',
                onSlot:s=>window.selectedSlot=s,onTimeSelect:()=>{}};
            window.renderTestMode=mode=>root.replaceChildren(renderCalendar({...options,mobileView:mode}));
            window.renderTestMode('week');
        }''', short)
        lectures = page.locator('[data-event-type="lecture"]')
        assert lectures.count() == 2
        consultation = page.locator('[data-slot-id="201"]')
        cb = consultation.bounding_box()
        for lecture in lectures.all():
            lb = lecture.bounding_box()
            assert lb['y'] + lb['height'] <= cb['y'] + 1 or cb['y'] + cb['height'] <= lb['y'] + 1
            assert abs(lb['width'] - cb['width']) <= 2
        consultation.click()
        assert page.evaluate('selectedSlot.id') == 201
        lectures.first.click()
        assert page.evaluate('selectedSlot === originalLecture')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(SHOTS / f'consultation_priority_{width}_{short}.png'), full_page=True)
        if width == 390:
            page.evaluate("renderTestMode('timeline')")
            assert lectures.count() == 2
            cb = consultation.bounding_box()
            for lecture in lectures.all():
                lb = lecture.bounding_box()
                assert lb['y'] + lb['height'] <= cb['y'] + 1 or cb['y'] + cb['height'] <= lb['y'] + 1
                assert abs(lb['width'] - cb['width']) <= 2
            consultation.click()
            assert page.evaluate('selectedSlot.id') == 201
            lectures.first.click()
            assert page.evaluate('selectedSlot === originalLecture')
            page.evaluate("renderTestMode('list')")
            # Fully covered lectures stay available in the list for management.
            assert page.locator('[data-event-type="lecture"]').count() == 2
            assert page.locator('[data-slot-id="102"]').is_visible()
    finally:
        page.close()
