"""Minimum 11–16 axis, while retaining earlier/later consultation cards."""
import os

import pytest

from tests.e2e.test_e2e import SHOTS, browser, server  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('width', [1280, 390])
def test_minimum_axis_and_outside_events(server, browser, width):  # noqa: F811
    base, _ = server
    page = browser.new_page(viewport={'width': width, 'height': 900})
    try:
        page.goto(base + '/static/offline.html')
        page.add_style_tag(url=base + '/static/css/app.css')
        for start, end, first, last in [
            (None, None, '11:00', '15:00'),
            ('13:00', '13:30', '11:00', '15:00'),
            ('14:20', '14:40', '11:00', '15:00'),
            ('09:00', '09:30', '08:00', '15:00'),
            ('16:00', '17:30', '11:00', '18:00'),
        ]:
            page.evaluate('''async ([start,end]) => {
                const {renderCalendar} = await import('/static/js/components/week-calendar.js');
                const root = document.createElement('main'); root.className = 'view';
                document.body.replaceChildren(root);
                const slots = start ? [{id: 1, capacity: 1, remaining: 1, kind: 'individual',
                    status: 'open', bookable: true, start_at: `2026-11-16T${start}:00+09:00`,
                    end_at: `2026-11-16T${end}:00+09:00`}] : [];
                root.append(renderCalendar({weekStart:'2026-11-16',slots,mobileView:'week',
                    onSlot:()=>{},onTimeSelect:()=>{}}));
            }''', [start, end])
            hours = page.locator('.week-grid .hour').all_text_contents()
            assert hours[0] == first and hours[-1] == last
            assert '11:00' in hours and '15:00' in hours
            hour = page.locator('.week-grid .hour').first.bounding_box()
            assert hour['height'] == pytest.approx(60 if width > 720 else 96, abs=1)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            if start:
                card = page.locator('[data-slot-id="1"]')
                assert card.is_visible()
                bounds = card.bounding_box()
                if start == '14:20' and width > 720:
                    assert not card.locator('.slot-time-end').is_visible()
                    assert '14:40' in card.get_attribute('aria-label')
                    label = card.locator('.slot-meta').bounding_box()
                    assert bounds['y'] <= label['y']
                    assert label['y'] + label['height'] <= bounds['y'] + bounds['height']
                grid = page.locator('.week-grid').bounding_box()
                assert bounds['y'] >= grid['y']
                assert bounds['y'] + bounds['height'] <= grid['y'] + grid['height'] + 1
            else:
                page.screenshot(path=str(SHOTS / f'minimum_calendar_{width}.png'), full_page=True)
    finally:
        page.close()
