"""실제 브라우저(Chromium) E2E. 개발용 로그인을 사용하며 실제 Google 로그인은 검증하지 않는다.

실행: RUN_E2E=1 pytest tests/e2e  (스크린샷: E2E_SHOTS 디렉터리, 기본 ./e2e-shots)
"""
from __future__ import annotations

import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from app.db import utcnow
from app.timeutil import today_kst

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")
ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(os.getenv("E2E_SHOTS", ROOT / "e2e-shots"))
PC = {"width": 1366, "height": 900}
MOBILE = {"width": 390, "height": 844}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db = tmp_path_factory.mktemp("e2e") / "e2e.db"
    port = _free_port()
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db}",
           "ADMIN_EMAILS": "admin@test.ac.kr", "PROFESSOR_EMAILS": "prof@test.ac.kr"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True,
                   capture_output=True)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
                             "--port", str(port), "--log-level", "warning"], cwd=ROOT, env=env)
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            if httpx.get(f"{base}/healthz").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    SHOTS.mkdir(parents=True, exist_ok=True)
    yield base, db
    proc.terminate()
    proc.wait(5)


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


class Session:
    def __init__(self, browser, base, email, viewport):
        self.ctx = browser.new_context(viewport=viewport, locale="ko-KR", timezone_id="Asia/Seoul")
        self.page = self.ctx.new_page()
        self.errors: list[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text)
                     if m.type == "error" and "401" not in m.text and "409" not in m.text else None)
        self.base = base
        self.page.goto(base + "/")
        self.page.fill("input[name=email]", email)
        self.page.click("text=개발용 로그인")
        self.page.wait_for_selector("#nav a", state="attached")
        # 로그인 직후 홈('/') → 역할별 첫 화면 리디렉션이 끝날 때까지 대기
        self.page.wait_for_selector('body[data-ready]:not([data-ready=""]):not([data-ready="/"])', state="attached")

    def go(self, path):
        self.page.goto(f"{self.base}/#{path}")
        # CSP가 eval을 막으므로 wait_for_function 대신 속성 선택자로 대기
        self.page.wait_for_selector(f'body[data-ready="{path}"]', state="attached")

    def shot(self, name):
        self.page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)

    def toast(self, text):
        self.page.wait_for_selector(f".toast:has-text('{text}')")

    def close(self):
        assert self.errors == [], self.errors
        self.ctx.close()


SLOT_DAY = today_kst(utcnow()) + timedelta(days=2)


def _create_slots_via_ui(s: Session, start="10:00", end="11:00", kind="individual", cap=None, duration=30):
    s.go("/slots")
    form = s.page.locator("form.grid-form")
    form.locator("input[type=date]").fill(SLOT_DAY.isoformat())
    times = form.locator("input[type=time]")
    times.nth(0).fill(start)
    times.nth(1).fill(end)
    form.locator("input[type=number]").nth(0).fill(str(duration))
    if kind == "group":
        form.locator("select").select_option("group")
        form.locator("input[type=number]").nth(2).fill(str(cap))
    form.locator("button[type=submit]").click()
    s.page.locator(".modal button:text-is('등록 확정')").click()
    s.toast("등록")


def _find_slot(s: Session, mobile=False):
    """학생 화면에서 SLOT_DAY의 예약 가능 슬롯을 찾는다 (필요 시 다음 주로 이동)."""
    for _ in range(2):
        if mobile:
            chip = s.page.locator(".chip").filter(has=s.page.locator(f"strong:text-is('{SLOT_DAY.day:02d}')"))
            if chip.count():
                chip.first.click()
                s.page.wait_for_timeout(300)
        loc = s.page.locator(".slot.open")
        if loc.count():
            return loc.first
        s.page.click("button[aria-label='다음 주']")
        s.page.wait_for_timeout(400)
    raise AssertionError("예약 가능한 슬롯을 찾지 못함")


def test_student_booking_flow_pc(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    _create_slots_via_ui(prof)
    prof.shot("pc_01_prof_slots")
    prof.close()

    st = Session(browser, base, "student1@test.ac.kr", PC)
    st.go("/booking")
    assert st.page.locator(".week-grid").is_visible()
    slot = _find_slot(st)
    st.shot("pc_02_student_calendar")
    slot.click()
    st.page.fill(".modal input[placeholder='학생 이름']", "김테스트")
    st.page.fill(".modal input[placeholder^='학번']", "20260001")
    st.page.locator(".modal select").nth(0).select_option("2")
    st.page.locator(".modal select").nth(1).select_option("career")
    st.page.locator(".modal select").nth(2).select_option("online")
    st.page.fill(".modal textarea", "진로 상담 희망")
    st.page.click(".modal button:text-is('예약하기')")
    st.toast("예약이 완료")
    st.page.wait_for_selector(".slot.mine")  # 토스트 이후 재렌더링 완료 대기
    assert st.page.locator(".slot.mine").count() == 1
    st.shot("pc_03_student_booked")
    st.go("/my-bookings")
    assert st.page.locator(".card.booking.booked").count() == 1
    assert "진로 · 온라인" in st.page.locator(".card.booking.booked").inner_text()
    with st.page.expect_download() as info:
        st.page.get_by_role("button", name="내 달력에 추가").click()
    assert info.value.suggested_filename.endswith(".ics")
    # Professor sees student-entered details; do not expose the professor's private note.
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/bookings")
    assert prof.page.locator(".week-grid").is_visible()
    prof.page.locator(".slot.reserved").first.click()
    assert "김테스트" in prof.page.locator(".modal").inner_text()
    prof.page.locator(".modal textarea").fill("학생 상담 테스트 기록")
    prof.page.locator(".modal button:text-is('기록 저장')").click()
    prof.toast("상담 기록을 저장")
    prof.go("/staff/insights")
    assert prof.page.locator("#staff-overview .insight-metric").count() >= 5
    note_card = prof.page.locator(".consult-note-card:has-text('학생 상담 테스트 기록')")
    note_card.wait_for(state="visible")
    assert "김테스트" in note_card.inner_text()
    note_card.get_by_role("button", name="상담 기록 수정").click()
    prof.page.locator(".modal textarea").fill("수정된 비공개 상담 기록")
    prof.page.locator(".modal button:text-is('확인')").click()
    prof.page.wait_for_selector(".consult-note-card:has-text('수정된 비공개 상담 기록')")
    prof.shot("pc_11_staff_insights")
    prof.go("/bookings")
    prof.page.get_by_role("button", name="예약 목록").click()
    assert "20260001" in prof.page.locator("tr:has-text('김테스트')").inner_text()
    prof.close()
    st.page.click("text=예약 취소")
    st.page.click(".modal button:text-is('취소하기')")
    st.toast("예약을 취소")
    st.page.wait_for_selector(".card.booking.cancelled")
    st.shot("pc_04_student_cancelled")
    st.close()


def test_week_calendar_time_scale_is_stable_across_durations(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    _create_slots_via_ui(prof, start="12:00", end="12:30", duration=30)
    _create_slots_via_ui(prof, start="13:00", end="14:00", duration=60)
    half_hour = prof.page.locator(".slot").filter(has=prof.page.locator(".slot-time:has-text('12:00')")).first
    full_hour = prof.page.locator(".slot").filter(has=prof.page.locator(".slot-time:has-text('13:00')")).first
    h30 = half_hour.bounding_box()["height"]
    h60 = full_hour.bounding_box()["height"]
    # Both have 1px top/bottom margins; the underlying 15-minute tracks
    # must make 60 minutes exactly twice the height of 30 minutes.
    assert abs((h60 + 2) - 2 * (h30 + 2)) <= 1, (h30, h60)
    prof.close()


def test_double_click_creates_single_booking(server, browser):
    base, _ = server
    st = Session(browser, base, "student2@test.ac.kr", PC)
    st.go("/booking")
    _find_slot(st).click()
    btn = st.page.locator(".modal button:text-is('예약하기')")
    btn.evaluate("(el) => { el.click(); el.click(); }")  # rapid duplicate is ignored during pending
    st.toast("예약이 완료")
    st.go("/my-bookings")
    assert st.page.locator(".card.booking.booked").count() == 1
    st.close()


def test_professor_completes_consultation(server, browser):
    base, db = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/bookings")
    prof.page.get_by_role("button", name="예약 목록").click()
    row = prof.page.locator("tr:has-text('student2@test.ac.kr')")
    row.wait_for(state="visible")
    assert row.count() == 1
    # 상담 시작 시각을 과거로 옮겨 '완료' 처리 상황 재현 (E2E 전용 DB 직접 수정)
    past = (utcnow() - timedelta(minutes=30)).replace(tzinfo=None).isoformat(" ")
    with sqlite3.connect(db) as c:
        bid = c.execute("select b.id from bookings b join users u on u.id=b.student_id "
                        "where u.email='student2@test.ac.kr' and b.status='booked'").fetchone()[0]
        c.execute("update slots set start_at=?, end_at=? where id=(select slot_id from bookings where id=?)",
                  (past, (utcnow() - timedelta(minutes=1)).replace(tzinfo=None).isoformat(" "), bid))
    prof.go("/bookings")
    prof.page.locator("select").nth(0).select_option("")  # 전체 상태
    prof.page.wait_for_timeout(400)
    prof.page.locator(f"tr[data-booking-id='{bid}'] details.action-more summary").click()
    prof.page.locator(f"tr[data-booking-id='{bid}'] >> text=완료").click()
    prof.toast("완료 처리")
    prof.page.locator("select").nth(0).select_option("")
    prof.page.wait_for_timeout(400)
    assert prof.page.locator(f"tr[data-booking-id='{bid}'] .badge.completed").count() == 1
    prof.shot("pc_05_prof_bookings")
    prof.close()


def test_admin_uses_professor_features_and_changes_role(server, browser):
    base, _ = server
    adm = Session(browser, base, "admin@test.ac.kr", PC)
    nav = adm.page.locator("#nav").inner_text()
    for label in ("상담 시간", "예약 관리", "상담 정보", "설문", "건의함", "계정·권한", "운영 설정", "작업 이력"):
        assert label in nav
    _create_slots_via_ui(adm, start="15:00", end="16:00", kind="group", cap=3)
    adm.go("/admin/users")
    row = adm.page.locator("tr[data-user-email='student1@test.ac.kr']")
    row.locator("select").select_option("professor")
    adm.page.click(".modal button:text-is('변경')")
    adm.toast("변경했습니다")
    adm.shot("pc_06_admin_users")
    adm.go("/admin/audit")
    assert "user.role_change" in adm.page.locator("table").inner_text()
    adm.close()
    # 강등·승격된 사용자는 기존 세션이 무효화되어 재로그인 시 새 역할
    s1 = Session(browser, base, "student1@test.ac.kr", PC)
    assert "예약 관리" in s1.page.locator("#nav").inner_text()
    s1.close()


def test_survey_create_submit_results(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/surveys/edit/new")
    prof.page.fill(".title-input", "중간 강의 설문")
    prof.page.locator("input[placeholder^='교과목']").fill("항공서비스 실무")
    prof.page.locator("input[placeholder^='학기']").fill("2026-2")
    prof.page.locator("input[type=number]").fill("1")  # 결과 공개 최소 응답 수
    prof.page.click("text=+ 문항 추가")
    prof.page.locator(".q-title").nth(0).fill("수업 만족도")
    prof.page.locator(".q-card select").nth(0).select_option("scale5")
    prof.page.click("text=+ 문항 추가")
    prof.page.locator(".q-title").nth(1).fill("좋았던 점")
    prof.page.locator(".q-card select").nth(1).select_option("multi")
    prof.page.click("text=+ 문항 추가")
    prof.page.locator(".q-title").nth(2).fill("하고 싶은 말")
    prof.page.locator(".q-card select").nth(2).select_option("long")
    prof.page.click("text=초안 저장")
    prof.page.wait_for_url(re.compile(r".*/surveys/edit/\d+$"))
    sid = prof.page.url.rsplit("/", 1)[1]
    prof.page.wait_for_selector(".q-title")
    prof.page.click("text=미리보기")
    assert prof.page.locator(".preview-banner").is_visible()
    prof.shot("pc_07_survey_preview")
    prof.page.click("text=편집으로")
    prof.page.click(".toolbar >> text=게시")
    prof.page.click(".modal button:text-is('게시')")
    prof.toast("게시했습니다")
    prof.page.wait_for_selector(".notice:has-text('게시된 설문')")
    prof.shot("pc_08_survey_published")

    st = Session(browser, base, "student3@test.ac.kr", PC)
    st.go("/surveys")
    assert "항공서비스 실무" in st.page.locator("main").inner_text()
    assert "2026-2" in st.page.locator("main").inner_text()
    st.page.click("text=응답하기")
    st.page.locator(".scale-item").nth(3).click()
    st.page.locator(".choices .check").nth(0).click()
    st.page.fill("textarea", "실습이 좋았어요")
    st.page.click("button:has-text('제출')")
    st.page.wait_for_selector(".notice.success")
    st.go("/surveys")
    assert st.page.locator(".badge:has-text('참여 완료')").count() == 1
    st.close()

    prof.go(f"/surveys/results/{sid}")
    assert "응답 1건" in prof.page.locator(".page-head").inner_text()
    assert "실습이 좋았어요" in prof.page.locator("main").inner_text()
    assert "student3" not in prof.page.locator("main").inner_text()
    prof.shot("pc_09_survey_results")
    prof.close()


def test_suggestion_flow(server, browser):
    base, _ = server
    st = Session(browser, base, "student4@test.ac.kr", PC)
    st.go("/suggestions")
    st.page.locator("select").select_option("assignment")
    st.page.fill("textarea", "<b>과제 마감</b>을 조금 늦춰 주세요")
    st.page.click("text=익명으로 제출")
    st.toast("익명으로 접수")
    st.close()
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/suggestions")
    card = prof.page.locator(".card:has-text('과제 마감')")
    assert card.count() == 1
    assert card.locator("b").count() == 0  # HTML이 해석되지 않고 글자로 표시됨 (XSS 방지)
    prof.page.click("text=반복 의견 분석")
    prof.page.wait_for_selector(".analysis")
    prof.shot("pc_10_prof_suggestions")
    prof.close()


def test_mobile_student_flow(server, browser):
    base, _ = server
    st = Session(browser, base, "mobile1@test.ac.kr", MOBILE)
    st.go("/booking")
    assert st.page.locator(".day-chips").is_visible()
    assert st.page.locator(".week-grid").count() == 0
    slot = _find_slot(st, mobile=True)
    st.page.get_by_role("button", name="일간 시간표 보기").click()
    st.page.locator(".day-timeline").wait_for(state="visible")
    assert st.page.locator(".day-timeline-slot.slot.open").count() > 0
    assert st.page.locator(".day-timeline-slot.slot.open").first.bounding_box()["height"] >= 44
    st.page.get_by_role("group", name="일정 보기 방식").get_by_role("button", name="목록 보기").click()
    st.page.locator(".daily .cards").wait_for(state="visible")
    slot = _find_slot(st, mobile=True)
    st.shot("mobile_01_daily")
    slot.click()
    st.page.keyboard.press("Escape")
    assert st.page.locator(".modal").count() == 0
    _find_slot(st, mobile=True).click()
    st.page.click(".modal button:text-is('예약하기')")
    st.toast("예약이 완료")
    st.page.wait_for_selector(".card.slot.mine")
    st.shot("mobile_02_booked")
    st.page.click("#menu-btn")
    st.page.click("#nav >> text=내 예약")
    st.page.wait_for_selector(".card.booking.booked")
    btn = st.page.locator("text=예약 취소").bounding_box()
    assert btn and btn["height"] >= 40  # 터치하기 쉬운 크기
    st.shot("mobile_03_my_bookings")
    st.go("/suggestions")
    st.page.fill("textarea", "모바일에서 제출")
    st.page.click("text=익명으로 제출")
    st.toast("익명으로 접수")
    st.close()


def test_mobile_staff_insights_and_timetable(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go("/staff/insights")
    assert prof.page.locator("#staff-overview .insight-metric").count() >= 5
    assert prof.page.get_by_text("전체 상담 기록", exact=True).is_visible()
    assert prof.page.locator(".consult-note-card").count() >= 1
    assert prof.page.locator("#mobile-tabs").is_visible()
    assert prof.page.evaluate("document.documentElement.scrollWidth") <= MOBILE["width"] + 1

    prof.go("/bookings")
    day_chip = prof.page.locator(".chip").filter(
        has=prof.page.locator(f"strong:text-is('{SLOT_DAY.day:02d}')"))
    if not day_chip.count():
        prof.page.click("button[aria-label='다음 주']")
        day_chip = prof.page.locator(".chip").filter(
            has=prof.page.locator(f"strong:text-is('{SLOT_DAY.day:02d}')"))
    day_chip.first.click()
    prof.page.get_by_role("button", name="일간 시간표 보기").click()
    prof.page.locator(".day-timeline").wait_for(state="visible")
    assert prof.page.locator(".day-timeline-slot").count() >= 1
    prof.page.get_by_role("group", name="일정 보기 방식").get_by_role("button", name="목록 보기").click()
    prof.page.locator(".daily .cards").wait_for(state="visible")
    prof.close()


def test_mobile_professor_views(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    for path, name in (("/slots", "mobile_04_prof_slots"), ("/bookings", "mobile_05_prof_bookings"),
                       ("/surveys", "mobile_06_prof_surveys")):
        prof.go(path)
        if path == "/slots":
            assert prof.page.locator(".day-chips").is_visible()
            assert prof.page.locator("form.grid-form").count() == 0
            assert prof.page.locator("#mobile-tabs").is_visible()
            assert prof.page.locator(".topbar").bounding_box()["height"] < 100
            prof.page.get_by_role("button", name="+ 상담 시간 등록").click()
            datebox = prof.page.locator(".inline-form input[type=date]").bounding_box()
            assert datebox and datebox["height"] < 70
        width = prof.page.evaluate("document.documentElement.scrollWidth")
        assert width <= MOBILE["width"] + 1, f"{path} 가로 스크롤 발생: {width}"
        prof.shot(name)
    prof.close()
