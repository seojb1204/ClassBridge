"""DB 없이 검증하는 순수 로직 단위 테스트."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.config import ConfigError, Settings
from app.core.errors import BadRequest, Conflict, TooManyRequests
from app.core.middleware import AnonymousAccessLogFilter
from app.core.permissions import ADMIN, PROFESSOR, STUDENT, P, has_permission
from app.core.rate_limit import RateLimiter
from app.infra.ai_client import scrub
from app.infra.excel import sanitize_cell
from app.models import Question
from app.services import booking_policy as bp
from app.services.survey_service import QuestionInput, _validate_answer, validate_questions

NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
POL = bp.Policy(booking_window_days=30, booking_deadline_hours=3, cancel_deadline_hours=3)


# ── 권한 ──
def test_admin_is_superset_of_professor():
    assert PROFESSOR < ADMIN


def test_student_has_no_staff_permissions():
    assert STUDENT & PROFESSOR == {P.SLOT_VIEW}


def test_professor_lacks_admin_only():
    for perm in (P.USER_MANAGE, P.ROLE_MANAGE, P.SETTINGS_MANAGE, P.AUDIT_VIEW):
        assert not has_permission("professor", perm) and has_permission("admin", perm)


def test_unknown_role_denied():
    assert not any(has_permission("superuser", p) for p in P)


def test_no_deanonymization_permission_exists():
    assert not [p for p in P if any(k in p.value for k in ("identify", "deanon", "trace", "author"))]


# ── 예약 정책 ──
def test_generate_blocks_with_break():
    blocks = bp.generate_blocks([date(2026, 11, 10)], time(10), time(11), 20, 10)
    starts = [b[0].astimezone(timezone(timedelta(hours=9))).strftime("%H:%M") for b in blocks]
    assert starts == ["10:00", "10:30"]


def test_generate_blocks_kst_to_utc():
    (st, en), = bp.generate_blocks([date(2026, 11, 10)], time(9), time(9, 30), 30, 0)
    assert st == datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)
    assert en - st == timedelta(minutes=30)


@pytest.mark.parametrize("dur,brk,start,end", [(3, 0, time(10), time(11)), (30, -1, time(10), time(11)),
                                               (30, 0, time(11), time(10)), (90, 0, time(10), time(11))])
def test_generate_blocks_invalid(dur, brk, start, end):
    with pytest.raises(BadRequest):
        bp.generate_blocks([date(2026, 11, 10)], start, end, dur, brk)


def test_expand_days_weekly():
    days = bp.expand_days(date(2026, 11, 2), [0, 2], 2)  # 월·수 × 2주
    assert [d.isoformat() for d in days] == ["2026-11-02", "2026-11-04", "2026-11-09", "2026-11-11"]


def test_booking_deadline_boundaries():
    bp.check_student_booking_time(NOW + timedelta(hours=3), NOW, POL)  # 정확히 3시간 전: 허용
    with pytest.raises(Conflict):
        bp.check_student_booking_time(NOW + timedelta(hours=2, minutes=59), NOW, POL)
    with pytest.raises(Conflict):
        bp.check_student_booking_time(NOW - timedelta(minutes=1), NOW, POL)
    with pytest.raises(Conflict):
        bp.check_student_booking_time(NOW + timedelta(days=30, minutes=1), NOW, POL)


def test_cancel_deadline_boundaries():
    bp.check_student_cancel_time(NOW + timedelta(hours=3), NOW, POL)
    with pytest.raises(Conflict):
        bp.check_student_cancel_time(NOW + timedelta(hours=2), NOW, POL)


def test_transitions():
    bp.check_transition("booked", "completed")
    bp.check_transition("completed", "no_show")
    for cur, tgt in (("cancelled", "booked"), ("cancelled", "completed"), ("completed", "cancelled")):
        with pytest.raises(Conflict):
            bp.check_transition(cur, tgt)


# ── 설문 입력값 ──
def _q(qtype, required=False, options=None):
    return Question(id=1, position=0, qtype=qtype, title="q", required=required, options=options or [])


def test_validate_answers():
    assert _validate_answer(_q("short"), "  hi ") == "hi"
    assert _validate_answer(_q("short"), "") is None
    with pytest.raises(BadRequest):
        _validate_answer(_q("short", required=True), "   ")
    assert _validate_answer(_q("multi", options=["a", "b", "c"]), ["c", "a"]) == ["a", "c"]
    with pytest.raises(BadRequest):
        _validate_answer(_q("multi", options=["a", "b"]), ["a", "a"])
    with pytest.raises(BadRequest):
        _validate_answer(_q("scale5"), True)
    assert _validate_answer(_q("scale5"), 5) == 5
    with pytest.raises(BadRequest):
        _validate_answer(_q("long"), "x" * 5001)


def test_validate_questions_strips_options_for_text():
    out = validate_questions([QuestionInput("short", " 제목 ", True, ["a", "b"])])
    assert out[0].title == "제목" and out[0].options == []


# ── 보안 유틸 ──
@pytest.mark.parametrize("v", ["=1+1", "+cmd", "-2+3", "@SUM(A1)", "\t=x", " =x"])
def test_excel_sanitize(v):
    assert sanitize_cell(v).startswith("'")


def test_excel_sanitize_keeps_normal():
    assert sanitize_cell("좋아요") == "좋아요" and sanitize_cell(3) == 3


def test_scrub_pii():
    out = scrub("메일 hong@school.ac.kr 전화 010-1234-5678 학번 20231234")
    assert "hong@" not in out and "010-1234" not in out and "20231234" not in out


def test_rate_limiter_window():
    t = [0.0]
    rl = RateLimiter([(2, 60)], clock=lambda: t[0])
    rl.hit("k")
    rl.hit("k")
    with pytest.raises(TooManyRequests):
        rl.hit("k")
    t[0] = 61
    rl.hit("k")


def test_access_log_filter_hides_anonymous_posts():
    f = AnonymousAccessLogFilter()

    def rec(method, path):
        return logging.LogRecord("uvicorn.access", 20, "", 0, '%s - "%s %s HTTP/%s" %d',
                                 ("1.2.3.4", method, path, "1.1", 201), None)

    assert not f.filter(rec("POST", "/api/surveys/3/responses"))
    assert not f.filter(rec("POST", "/api/public-surveys/abc/responses"))
    assert not f.filter(rec("GET", "/api/public-surveys/abc"))
    assert not f.filter(rec("POST", "/api/suggestions"))
    assert f.filter(rec("GET", "/api/suggestions"))
    assert f.filter(rec("POST", "/api/bookings"))


def test_production_config_rejects_unsafe():
    with pytest.raises(ConfigError) as e:
        Settings(env="production", dev_login_enabled=True).validate()
    msg = str(e.value)
    for key in ("DEV_LOGIN_ENABLED", "SECRET_KEY", "COOKIE_SECURE", "PostgreSQL", "GOOGLE_CLIENT_ID", "ADMIN_EMAILS"):
        assert key in msg


def test_production_config_ok():
    Settings(env="production", database_url="postgresql://x", secret_key="k" * 40, cookie_secure=True,
             google_client_id="id", google_client_secret="sec", admin_emails=["a@x"]).validate()
