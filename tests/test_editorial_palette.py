"""The Editorial Campus palette remains legible without making every surface white."""
import re
from pathlib import Path

import pytest

CSS = (Path(__file__).resolve().parents[1] / 'static/css/app.css').read_text()
TOKENS = dict(re.findall(r'--([\w-]+): (#[0-9a-f]{6})', CSS))


def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * w for v, w in zip(channels, [.2126, .7152, .0722]))


def contrast(a, b):
    low, high = sorted([luminance(a), luminance(b)])
    return (high + .05) / (low + .05)


@pytest.mark.parametrize('fg,bg', [
    ('text', 'bg'), ('muted', 'bg'), ('muted', 'panel'),
    ('primary', 'bg'), ('primary', 'primary-weak'),
    ('danger', 'danger-weak'), ('mine', 'mine-weak'),
    ('available', 'available-bg'),
])
def test_normal_text_palette_meets_wcag_aa(fg, bg):
    assert contrast(TOKENS[fg], TOKENS[bg]) >= 4.5


@pytest.mark.parametrize('bg', ['primary', 'booking-mine', 'mine', 'danger'])
def test_filled_buttons_have_legible_white_text(bg):
    assert contrast('#ffffff', TOKENS[bg]) >= 4.5


def test_focus_and_input_boundaries_have_three_to_one_contrast():
    assert contrast(TOKENS['primary'], TOKENS['bg']) >= 3
    assert contrast('#9c8f7e', TOKENS['panel']) >= 3
