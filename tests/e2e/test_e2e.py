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
from datetime import datetime, timedelta
from datetime import time as daytime
from pathlib import Path

import httpx
import pytest

from app.db import utcnow
from app.timeutil import KST, today_kst

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E 미설정")
ROOT = Path(__file__).resolve().parents[2]
SHOTS = Path(os.getenv("E2E_SHOTS", ROOT / "e2e-shots"))
PC = {"width": 1366, "height": 900}
MOBILE = {"width": 390, "height": 844}


def test_staff_booking_activity_mobile_filter_pagination_and_student_access(server, browser):
    base, _ = server
    for role in ('prof@test.ac.kr', 'admin@test.ac.kr'):
        s = Session(browser, base, role, MOBILE, service_workers='block')
        page = s.page
        event = {'id': 30, 'booking_id': 7, 'action': 'cancel', 'actor_name': '학생 테스트',
                 'student_name': '<script>테스트</script>', 'actor_is_student': True,
                 'at': '2026-11-07T01:02:03Z', 'start_at': '2026-11-10T04:00:00Z',
                 'status': 'cancelled', 'detail': ''}

        def activity(route, request, event=event):
            if 'before_id=' in route.request.url:
                route.fulfill(json={'items': [{**event, 'id': 20}], 'next_before_id': None})
            elif 'kind=change' in route.request.url:
                route.fulfill(json={'items': [], 'next_before_id': None})
            else:
                route.fulfill(json={'items': [event], 'next_before_id': 30})

        page.route('**/api/staff/booking-events?*', activity)
        s.go('/bookings')
        page.get_by_role('button', name='예약 활동 기록', exact=True).click()
        panel = page.locator('.booking-activity')
        panel.get_by_text('학생 예약 취소', exact=True).wait_for()
        assert panel.get_by_text('처리자: 학생 테스트 (예약 학생 본인)').count() == 1
        assert panel.locator('script').count() == 0
        panel.get_by_role('button', name='이전 기록 더 보기').click()
        panel.get_by_text('2건 표시 · 최신 기록부터', exact=True).wait_for()
        s.shot('mobile_booking_activity_' + role.split('@')[0])
        panel.get_by_label('활동 종류').select_option('change')
        panel.get_by_text('해당 예약 활동 기록이 없습니다.').wait_for()
        s.close()
    student = Session(browser, base, 'activity-student@test.ac.kr', MOBILE)
    student.page.goto(base + '/#/bookings')
    student.page.get_by_text('접근 권한이 없는 화면입니다.').wait_for()
    assert student.page.get_by_text('접근 권한이 없는 화면입니다.').count() == 1
    assert student.page.locator('.booking-activity').count() == 0
    student.close()


def test_live_booking_refresh_preserves_dialog_and_stops_after_navigation(server, browser):
    base, _ = server
    s = Session(browser, base, "live-refresh@test.ac.kr", MOBILE, service_workers="block")
    page = s.page
    day = (today_kst(utcnow()) + timedelta(days=1)).isoformat()
    slot = {"id": 99001, "start_at": f"{day}T10:00:00+09:00", "end_at": f"{day}T10:30:00+09:00",
            "kind": "individual", "capacity": 1, "remaining": 1, "status": "open", "bookable": True,
            "mine": False, "location": "m205", "note": "", "reason": ""}
    calls = []

    def slots(route):
        calls.append(route.request.url)
        route.fulfill(json=[slot])

    page.route("**/api/slots?*", slots)
    page.clock.install()
    page.reload()
    s.go("/booking")
    page.locator('[data-slot-id="99001"]').click()
    page.locator('.modal textarea').fill('작성 중인 상담 질문')
    before = len(calls)
    page.clock.run_for(31000)
    assert len(calls) == before
    assert page.locator('.modal textarea').input_value() == '작성 중인 상담 질문'
    page.keyboard.press('Escape')
    slot.update(remaining=0, bookable=False, reason="마감")
    page.clock.run_for(31000)
    page.locator('[data-slot-id="99001"]').filter(has_text="마감").wait_for()
    assert len(calls) > before
    s.shot("mobile_live_booking_refresh")
    s.go('/my-bookings')
    before = len(calls)
    page.clock.run_for(31000)
    assert len(calls) == before
    s.close()


def test_staff_today_and_actionable_notification_error(server, browser):
    base, _ = server
    s = Session(browser, base, 'admin@test.ac.kr', MOBILE, service_workers="block")
    p = s.page
    p.route('**/api/bookings?start=*&days=1&status=booked', lambda r: r.fulfill(json=[{}, {}]))
    p.route('**/api/suggestions/stats', lambda r: r.fulfill(json={"by_status": {"new": 3}}))
    p.route('**/api/surveys', lambda r: r.fulfill(json=[{"status": "published"}, {"status": "draft"}]))
    p.reload()
    s.go('/slots')
    assert p.locator('.staff-today').count() == 0
    s.go('/bookings')
    panel = p.locator('.staff-today')
    panel.get_by_role('link', name='오늘 예약 2건').wait_for()
    panel.get_by_role('link', name='새 건의 3건').wait_for()
    panel.get_by_role('link', name='진행 중 설문 1건').wait_for()
    s.shot('mobile_staff_today')
    p.route('**/api/admin/notifications', lambda r: r.fulfill(json={
        "enabled": True, "push_enabled": True, "push_devices": 0,
        "items": [{"id": 1, "booking_id": 1, "channel": "gmail", "status": "reauth",
                   "attempts": 1, "error_code": "token_rejected"}]}))
    s.go('/admin/settings')
    p.locator('.notification-help').filter(has_text='로그인용 설정은 변경하지 마세요').wait_for()
    s.shot('mobile_notification_recovery')
    s.close()


def test_mobile_day_selection_scroll_notice_order_and_student_no_export(server, browser):
    base, _ = server
    days = [(today_kst(utcnow()) + timedelta(days=i)).isoformat() for i in (1, 2)]
    slots = [{"id": 9500 + d * 10 + i, "start_at": f"{day}T{10 + i:02d}:00:00+09:00",
              "end_at": f"{day}T{10 + i:02d}:30:00+09:00", "kind": "individual", "capacity": 1,
              "remaining": 1, "status": "open", "bookable": True, "mine": False,
              "location": "m205", "note": "", "reason": ""}
             for d, day in enumerate(days) for i in range(6)]
    for email, path in [("scroll-student@test.ac.kr", "/booking"), ("prof@test.ac.kr", "/slots")]:
        session = Session(browser, base, email, MOBILE, service_workers="block")
        page = session.page
        page.emulate_media(reduced_motion="reduce")
        page.route("**/api/slots?*", lambda route: route.fulfill(json=slots))
        page.route("**/api/slots/available-days", lambda route: route.fulfill(
            json=[{"date": day, "count": 6} for day in days]))
        page.route("**/api/announcement", lambda route: route.fulfill(json={"announcement": {
            "title": "먼저 읽을 공지", "body": "상담 준비 안내입니다.\n" * 18, "published": True, "revision": 1}}))
        page.reload()
        session.go(path)
        page.get_by_role("heading", name="먼저 읽을 공지").wait_for()
        assert page.locator(".announcement-panel").bounding_box()["y"] < page.locator(".available-days").bounding_box()["y"]
        page.locator(".available-day-buttons button").nth(1).click()
        title = page.locator(".daily-title:focus")
        title.wait_for()
        assert page.locator('.chip[aria-selected="true"] strong').inner_text() == days[1][-2:]
        header = page.locator(".topbar").bounding_box()
        box = title.bounding_box()
        assert header["height"] <= box["y"] <= header["height"] + 30
        assert page.locator(".daily .cards .card").count() == 6
        session.shot("mobile_date_scroll_student" if path == "/booking" else "mobile_date_scroll_professor")
        if path == "/booking":
            session.go("/my-bookings")
            assert page.get_by_text("상담 자료 다운로드", exact=True).count() == 0
            assert page.locator(".export-panel").count() == 0
        session.close()


def test_editor_direct_trash_and_empty_account_cleanup(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go("/surveys/edit/new")
    prof.page.fill(".title-input", "바로 삭제 검증")
    prof.page.get_by_role("button", name="+ 문항 추가", exact=True).click()
    prof.page.locator(".q-title").fill("소감")
    prof.page.get_by_role("button", name="초안 저장", exact=True).click()
    prof.page.wait_for_url(re.compile(r".*/surveys/edit/\d+$"))
    prof.page.locator(".toolbar").get_by_role("button", name="게시", exact=True).click()
    prof.page.locator(".modal").get_by_role("button", name="게시", exact=True).click()
    prof.toast("게시했습니다")
    prof.page.locator(".toolbar").get_by_role("button", name="삭제", exact=True).click()
    prof.shot("mobile_survey_direct_delete")
    prof.page.locator(".modal").get_by_role("button", name="삭제", exact=True).click()
    prof.page.wait_for_url(re.compile(r".*/#/surveys$"))
    prof.page.get_by_role("button", name="휴지통", exact=True).click()
    card = prof.page.locator(".card").filter(has_text="바로 삭제 검증")
    card.get_by_role("button", name="복원", exact=True).click()
    prof.page.locator(".modal").get_by_role("button", name="확인", exact=True).click()
    card.wait_for(state="detached")
    prof.page.get_by_role("button", name="설문 목록", exact=True).click()
    prof.page.locator(".card").filter(has_text="바로 삭제 검증").get_by_text("종료", exact=True).wait_for()
    prof.close()
    student = Session(browser, base, "empty-delete@test.ac.kr", MOBILE)
    student.close()
    admin = Session(browser, base, "admin@test.ac.kr", PC)
    admin.go("/admin/users")
    row = admin.page.locator("tr[data-user-email='empty-delete@test.ac.kr']")
    row.get_by_role("button", name="계정 삭제", exact=True).click()
    admin.shot("pc_empty_account_delete")
    admin.page.locator(".modal").get_by_role("button", name="삭제", exact=True).click()
    admin.toast("학생 계정을 삭제했습니다")
    assert row.count() == 0
    admin.go("/admin/settings")
    admin.page.get_by_role("heading", name="예약 알림 상태", exact=True).wait_for()
    admin.shot("pc_notification_settings")
    admin.close()


def test_booking_announcement_mobile_lifecycle(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go("/slots")
    prof.page.get_by_role("button", name="공지 작성", exact=True).click()
    prof.page.get_by_label("공지 제목").fill("상담 전 준비 안내")
    prof.page.get_by_label("공지 내용").fill("질문을 정리해 주세요.\n<script>window.noticeInjected=true</script>")
    prof.page.get_by_role("button", name="공지 저장", exact=True).click()
    prof.toast("숨김 상태")
    student = Session(browser, base, "notice-student@test.ac.kr", MOBILE)
    student.go("/booking")
    assert student.page.locator(".announcement-panel").count() == 0
    prof.page.get_by_role("button", name="공지 수정", exact=True).click()
    prof.page.get_by_label("공개 상태").select_option("true")
    prof.page.get_by_role("button", name="공지 저장", exact=True).click()
    prof.toast("게시했습니다")
    student.page.reload()
    student.page.get_by_role("heading", name="상담 전 준비 안내").wait_for()
    assert student.page.locator(".announcement-body").inner_text().endswith("</script>")
    assert student.page.evaluate("window.noticeInjected === undefined")
    assert student.page.get_by_role("button", name="공지 수정").count() == 0
    assert student.page.evaluate("document.documentElement.scrollWidth") <= MOBILE["width"] + 1
    student.shot("mobile_booking_announcement")
    student.page.get_by_text("예약 방법·마감 시간", exact=True).click()
    student.page.get_by_text("‘예약 가능’ 시간을 눌러 예약하세요.", exact=False).wait_for()
    admin = Session(browser, base, "admin@test.ac.kr", PC)
    admin.go("/slots")
    admin.page.get_by_role("button", name="공지 수정", exact=True).click()
    admin.page.get_by_label("공개 상태").select_option("false")
    admin.page.get_by_role("button", name="공지 저장", exact=True).click()
    admin.toast("숨김 상태")
    student.page.reload()
    student.page.wait_for_selector('body[data-ready="/booking"]')
    assert student.page.locator(".announcement-panel").count() == 0
    prof.close()
    student.close()
    admin.close()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_anonymous_survey_qr_and_direct_response(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go("/surveys/edit/new")
    prof.page.fill(".title-input", "QR 익명 소감")
    prof.page.get_by_label("참여 방식").select_option("anonymous")
    prof.page.get_by_role("button", name="+ 문항 추가", exact=True).click()
    assert prof.page.locator(".q-card select option").evaluate_all("nodes => nodes.map(n => n.value)") == [
        "long", "scale5", "single"]
    prof.page.locator(".q-title").fill("이번 강의에서 개선할 점")
    prof.page.get_by_role("button", name="초안 저장", exact=True).click()
    prof.page.wait_for_url(re.compile(r".*/surveys/edit/\d+$"))
    prof.page.locator(".toolbar").get_by_role("button", name="게시", exact=True).click()
    prof.page.locator(".modal").get_by_role("button", name="게시", exact=True).click()
    prof.toast("게시했습니다")
    prof.page.get_by_role("button", name="QR 공유", exact=True).click()
    assert prof.page.evaluate("document.documentElement.scrollWidth") <= MOBILE["width"] + 1
    qr = prof.page.get_by_alt_text("학생 참여용 설문 QR 코드")
    qr.wait_for()
    qr.evaluate("img => img.decode()")
    assert qr.evaluate("img => img.naturalWidth > 0")
    prof.page.locator(".toast").last.wait_for(state="hidden")
    qr.screenshot(path=str(SHOTS / "anonymous_survey_qr.png"))
    prof.shot("mobile_survey_qr_share")
    link = prof.page.locator(".survey-share-url").get_attribute("href")
    assert "/#/surveys/public/" in link
    with prof.page.expect_download() as download:
        prof.page.get_by_role("link", name="QR 이미지 저장(PNG)", exact=True).click()
    assert download.value.suggested_filename.endswith("-qr.png")
    ctx = browser.new_context(viewport=MOBILE)
    page = ctx.new_page()
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(link)
    page.locator(".survey-form").wait_for()
    assert not any("/api/me" in url for url in requests)
    assert page.get_by_role("link", name="Google 계정으로 로그인").count() == 0
    page.fill("textarea", "사례 설명을 더 듣고 싶어요")
    page.get_by_role("button", name="제출", exact=True).click()
    page.locator(".notice.success").wait_for()
    page.reload()
    page.get_by_text("이 브라우저에서는 이미 참여한 설문입니다.", exact=False).wait_for()
    ctx.close()
    student = Session(browser, base, "anonymous-list@test.ac.kr", MOBILE)
    student.go("/surveys")
    card = student.page.locator(".card").filter(has_text="QR 익명 소감")
    card.get_by_text("계정과 연결하지 않습니다.", exact=False).wait_for()
    student_requests = []
    student.page.on("request", lambda r: student_requests.append(r.url))
    card.get_by_role("link", name="익명 설문 열기", exact=True).click()
    student.page.locator(".survey-form").wait_for()
    assert not any("/api/me" in url for url in student_requests)
    student.page.fill("textarea", "로그인 상태에서도 익명 참여")
    student.page.get_by_role("button", name="제출", exact=True).click()
    student.page.locator(".notice.success").wait_for()
    student.page.reload()
    student.page.get_by_text("이 브라우저에서는 이미 참여한 설문입니다.", exact=False).wait_for()
    student.close()
    prof.page.get_by_role("button", name="닫기", exact=True).click()
    prof.close()


def test_pwa_install_guide_all_bookings_and_private_offline(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go("/slots")
    prof.page.locator("#menu-btn").click()
    prof.page.get_by_role("button", name="앱 설치 안내", exact=True).click()
    prof.page.get_by_role("heading", name="안드로이드 앱 설치", exact=True).wait_for()
    prof.shot("mobile_pwa_install_guide")
    prof.page.get_by_role("button", name="확인", exact=True).click()
    prof.page.goto(base + "/#/staff/today")
    prof.page.wait_for_selector('body[data-ready="/bookings"]')
    prof.page.get_by_text("오늘 이후 · 현재 예약", exact=False).wait_for()
    assert prof.page.get_by_role("button", name="오늘 상담", exact=True).count() == 0
    assert prof.page.get_by_role("button", name="내일 상담", exact=True).count() == 0
    assert prof.page.locator("input[type=date]").count() == 0
    assert prof.page.evaluate("document.documentElement.scrollWidth") <= MOBILE["width"] + 1
    prof.shot("mobile_pwa_bookings")
    prof.page.evaluate("navigator.serviceWorker.ready")
    prof.page.reload()
    prof.page.wait_for_selector('body[data-ready="/bookings"]')
    cached = prof.page.evaluate("""async () => {
      const result = [];
      for (const key of await caches.keys()) {
        const cache = await caches.open(key);
        for (const request of await cache.keys()) result.push(new URL(request.url).pathname);
      }
      return result;
    }""")
    assert cached == ["/static/offline.html"]
    assert prof.errors == []
    prof.ctx.set_offline(True)
    prof.page.reload()
    prof.page.get_by_role("heading", name="인터넷 연결을 확인해 주세요").wait_for()
    assert "교수" not in prof.page.locator("body").inner_text()
    assert prof.page.evaluate("fetch('/api/bookings').then(() => false).catch(() => true)")
    assert all("ERR_INTERNET_DISCONNECTED" in error for error in prof.errors), prof.errors
    prof.errors.clear()
    prof.ctx.set_offline(False)
    prof.page.get_by_role("link", name="다시 연결하기").click()
    prof.page.wait_for_selector('body[data-ready="/slots"]')
    prof.close()
    student = Session(browser, base, "pwa-student@test.ac.kr", MOBILE)
    student.page.locator("#menu-btn").click()
    assert student.page.locator(".pwa-install").count() == 0
    student.close()


def test_pwa_standalone_staff_home(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.ctx.add_init_script("""(() => {
      const original = window.matchMedia.bind(window);
      window.matchMedia = query => query === '(display-mode: standalone)'
        ? {matches: true, addEventListener() {}} : original(query);
    })();""")
    prof.page.goto(base + "/")
    prof.page.wait_for_selector('body[data-ready="/bookings"]')
    assert prof.page.locator(".pwa-install").count() == 0
    prof.close()


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    db = tmp_path_factory.mktemp("e2e") / "e2e.db"
    port = _free_port()
    env = {**os.environ, "APP_ENV": "development", "DATABASE_URL": f"sqlite:///{db}", "BASE_URL": f"http://127.0.0.1:{port}",
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
    def __init__(self, browser, base, email, viewport, service_workers="allow"):
        self.ctx = browser.new_context(viewport=viewport, locale="ko-KR", timezone_id="Asia/Seoul",
                                       service_workers=service_workers)
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
    if s.page.locator("#mobile-tabs").is_visible():
        s.page.get_by_role("link", name="상담 등록", exact=True).click()
    elif s.page.get_by_role("button", name="+ 상담 시간 등록", exact=True).count():
        s.page.get_by_role("button", name="+ 상담 시간 등록", exact=True).click()
    form = s.page.locator("form.grid-form")
    form.get_by_label("날짜(시작일)", exact=True).fill(SLOT_DAY.isoformat())
    form.get_by_label("시작", exact=True).fill(start)
    form.get_by_label("종료", exact=True).fill(end)
    form.locator("input[type=number]").nth(0).fill(str(duration))
    if kind == "group":
        form.get_by_label("유형", exact=True).select_option("group")
        form.locator("input[type=number]").nth(2).fill(str(cap))
    form.locator("button[type=submit]").click()
    s.page.locator(".modal button:text-is('등록 확정')").click()
    s.toast("등록")
    form.wait_for(state="hidden")
    s.page.locator(".week-grid, .daily").wait_for()


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
    assert prof.page.get_by_role("heading", name="상담 불가일", exact=True).count() == 0
    prof.page.get_by_text("등록된 상담 시간만 예약할 수 있습니다.", exact=False).wait_for()
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
    assert st.page.get_by_text("건강·심리 상태 등 민감한 개인정보는 입력하지 마세요.", exact=False).is_visible()
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
    prof.page.get_by_role("button", name="주간 예약 시간표").click()
    prof.page.locator(".week-grid").wait_for(state="visible")
    # The fixture can fall in next week (e.g. when this test runs on Saturday).
    today = today_kst(utcnow())
    if SLOT_DAY - timedelta(days=SLOT_DAY.weekday()) > today - timedelta(days=today.weekday()):
        prof.page.get_by_role('button', name='다음 주', exact=True).click()
    prof.page.locator(".slot.reserved").first.click()
    assert "김테스트" in prof.page.locator(".modal").inner_text()
    assert prof.page.get_by_text("건강·심리 상태 등 민감한 개인정보는 입력하지 마세요.", exact=False).is_visible()
    prof.page.locator(".modal textarea").fill("학생 상담 테스트 기록")
    prof.page.locator(".modal button:text-is('기록 저장')").click()
    prof.toast("상담 기록을 저장")
    prof.go("/staff/insights")
    assert prof.page.locator("#nav").get_by_role("link", name="상담 정보").is_visible()
    assert prof.page.locator("#staff-overview .insight-metric").count() >= 5
    note_card = prof.page.locator(".consult-note-card:has-text('학생 상담 테스트 기록')")
    note_card.wait_for(state="visible")
    assert "김테스트" in note_card.inner_text()
    note_card.get_by_role("button", name="상담 기록 수정").click()
    assert prof.page.get_by_text("건강·심리 상태 등 민감한 개인정보는 입력하지 마세요.", exact=False).is_visible()
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
    # Keep the manual-completion fixture in today's list even just after KST
    # midnight. Leave its end in the future so automatic completion cannot race
    # this test of the professor's manual action (covered separately).
    now = utcnow()
    day_start = datetime.combine(today_kst(now), daytime.min, tzinfo=KST).astimezone(now.tzinfo)
    past = max(now - timedelta(minutes=30), day_start).replace(tzinfo=None).isoformat(" ", timespec="microseconds")
    with sqlite3.connect(db) as c:
        bid = c.execute("select b.id from bookings b join users u on u.id=b.student_id "
                        "where u.email='student2@test.ac.kr' and b.status='booked'").fetchone()[0]
        c.execute("update slots set start_at=?, end_at=? where id=(select slot_id from bookings where id=?)",
                  (past, (now + timedelta(minutes=5)).replace(tzinfo=None).isoformat(" ", timespec="microseconds"), bid))
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
    prof.page.locator(".q-title").nth(0).fill("강의 설명이 이해하기 쉬웠다")
    prof.page.locator(".q-card select").nth(0).select_option("scale5")
    prof.page.click("text=+ 문항 추가")
    prof.page.locator(".q-title").nth(1).fill("내일 만날 장소")
    prof.page.locator(".q-card select").nth(1).select_option("single")
    prof.page.locator(".options input").nth(0).fill("서울")
    prof.page.locator(".options input").nth(1).fill("강원")
    prof.page.click("text=+ 문항 추가")
    prof.page.locator(".q-title").nth(2).fill("하고 싶은 말")
    prof.page.locator(".q-card select").nth(2).select_option("long")
    prof.page.click("text=초안 저장")
    prof.page.wait_for_url(re.compile(r".*/surveys/edit/\d+$"))
    sid = prof.page.url.rsplit("/", 1)[1]
    prof.page.wait_for_selector(".q-title")
    prof.page.click("text=미리보기")
    assert prof.page.locator(".preview-banner").is_visible()
    # A previous calendar's layout listener must not overwrite this screen.
    prof.page.set_viewport_size(MOBILE)
    prof.page.locator(".preview-banner").wait_for(state="visible")
    prof.shot("mobile_survey_preview")
    prof.page.set_viewport_size(PC)
    prof.shot("pc_07_survey_preview")
    assert prof.page.locator(".preview-banner").is_visible()
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
    st.page.locator(".survey-form").wait_for(state="visible")
    assert st.page.get_by_text("참여는 선택입니다.", exact=False).is_visible()
    assert st.page.get_by_text("DB·서버 기록", exact=False).is_visible()
    st.page.locator(".scale-choices .check").nth(3).click()
    st.page.get_by_label("서울", exact=True).check()
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
    st.page.get_by_role("link", name="익명 건의하기", exact=True).click()
    st.page.get_by_text("이 건의는 Google 계정과 연결되지 않습니다.", exact=True).wait_for()
    assert st.page.get_by_text("DB·서버 기록", exact=False).count() == 0
    assert st.page.get_by_text("이름·학번·연락처나", exact=False).count() == 0
    st.shot("pc_student_suggestion_notice")
    st.page.get_by_label("유형", exact=False).select_option("assignment")
    st.page.fill("textarea", "<b>과제 마감</b>을 조금 늦춰 주세요")
    with st.page.expect_request("**/api/suggestions/anonymous") as sent:
        st.page.click("text=익명으로 제출")
    assert "cookie" not in sent.value.all_headers()
    assert "x-csrf-token" not in sent.value.all_headers()
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
    # The same restored inbox must hide analysis when deployment disables AI.
    def disabled_ai(route):
        response = route.fetch()
        data = response.json()
        data["features"]["ai"] = "disabled"
        route.fulfill(response=response, json=data)

    prof.page.route("**/api/me", disabled_ai)
    prof.page.reload()
    prof.page.wait_for_selector('body[data-ready="/suggestions"]', state="attached")
    assert prof.page.get_by_role("button", name="반복 의견 분석").count() == 0
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
    st.page.get_by_role("link", name="익명 건의하기", exact=True).click()
    st.page.fill("textarea", "모바일에서 제출")
    st.page.click("text=익명으로 제출")
    st.toast("익명으로 접수")
    st.close()


def test_mobile_staff_insights_and_timetable(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go("/staff/insights")
    tabs = prof.page.locator("#mobile-tabs")
    assert tabs.get_by_role("link", name="상담 정보").count() == 0
    assert prof.page.locator('.topbar button[aria-controls="nav"]').count() == 0
    assert prof.page.locator('.topbar button[aria-controls="inbox-popover"]').count() == 1
    tabs.get_by_role("button", name="더보기 메뉴").click()
    prof.page.locator("#nav").get_by_role("link", name="상담 정보").click()
    assert prof.page.locator("#staff-overview .insight-metric").count() >= 5
    assert prof.page.get_by_text("전체 상담 기록", exact=True).is_visible()
    assert prof.page.locator(".consult-note-card").count() >= 1
    assert prof.page.locator("#mobile-tabs").is_visible()
    assert prof.page.evaluate("document.documentElement.scrollWidth") <= MOBILE["width"] + 1

    prof.go("/bookings")
    prof.page.get_by_role("button", name="주간 예약 시간표").click()
    prof.page.locator(".day-chips").wait_for()
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
            assert prof.page.get_by_role("button", name="일간 시간표 보기").count() == 0
            assert prof.page.locator("form.grid-form").count() == 0
            assert prof.page.locator("#mobile-tabs").is_visible()
            assert prof.page.locator(".topbar").bounding_box()["height"] < 100
            prof.page.get_by_role("link", name="상담 등록", exact=True).click()
            assert prof.page.get_by_label("장소", exact=True).input_value() == "m205"
            datebox = prof.page.get_by_label("날짜(시작일)", exact=True).bounding_box()
            assert datebox and datebox["height"] < 70
        width = prof.page.evaluate("document.documentElement.scrollWidth")
        assert width <= MOBILE["width"] + 1, f"{path} 가로 스크롤 발생: {width}"
        prof.shot(name)
    prof.close()


def test_mobile_optional_sections_do_not_render_null(server, browser):
    base, _ = server
    for email, path in [("optional-student@test.ac.kr", "/booking"),
                        ("prof@test.ac.kr", "/slots")]:
        session = Session(browser, base, email, MOBILE)
        try:
            session.go(path)
            text = session.page.locator("#view").inner_text()
            assert "null" not in text.split()
            assert "undefined" not in text.split()
            if path == "/slots":
                session.page.get_by_role("link", name="상담 등록", exact=True).click()
                session.page.locator("#slot-create-panel").wait_for(state="visible")
                session.page.locator("#mobile-tabs").get_by_role("link", name="상담 시간", exact=True).click()
                session.page.locator("#slot-create-panel").wait_for(state="hidden")
                assert "null" not in session.page.locator("#view").inner_text().split()
            session.shot("optional_student" if path == "/booking" else "optional_professor")
        finally:
            session.close()


def test_public_suggestion_reply_trash_and_restore(server, browser):
    base, _ = server
    student = Session(browser, base, "public-board@test.ac.kr", MOBILE)
    student.go("/suggestions")
    student.page.get_by_role("link", name="익명 건의하기", exact=True).click()
    student.page.get_by_label("공개 범위", exact=False).select_option("public")
    student.page.locator("textarea").fill("공개 게시판 회귀 검증 의견")
    student.page.get_by_role("button", name="익명으로 제출").click()
    student.toast("익명으로 접수")
    student.page.get_by_role("link", name="공개 건의 게시판 (로그인 필요)").click()
    student.page.locator(".public-board .card").filter(has_text="공개 게시판 회귀 검증 의견").wait_for()
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/suggestions")
    card = prof.page.locator(".card").filter(has_text="공개 게시판 회귀 검증 의견")
    card.get_by_role("button", name="답변 달기").click()
    prof.page.locator(".modal textarea").fill("교수자 공개 답변 테스트")
    prof.page.locator(".modal").get_by_role("button", name="확인", exact=True).click()
    card.get_by_text("교수자 공개 답변 테스트").wait_for()
    student.page.reload()
    student.page.get_by_text("교수자 공개 답변 테스트").wait_for()
    student.shot("mobile_public_board")
    assert student.page.locator("body").evaluate("el => el.scrollWidth") <= MOBILE["width"]
    card.get_by_role("button", name="휴지통으로").click()
    prof.page.locator(".modal").get_by_role("button", name="확인", exact=True).click()
    prof.page.get_by_role("button", name="휴지통", exact=True).click()
    card.get_by_role("button", name="복원").wait_for()
    student.page.reload()
    student.page.locator(".public-board").wait_for()
    assert student.page.get_by_text("공개 게시판 회귀 검증 의견", exact=True).count() == 0
    prof.shot("suggestion_trash")
    card.get_by_role("button", name="복원").click()
    prof.page.locator(".modal").get_by_role("button", name="확인", exact=True).click()
    prof.page.get_by_role("button", name="건의 목록", exact=True).click()
    card.get_by_role("button", name="휴지통으로").wait_for()
    student.page.reload()
    student.page.get_by_text("교수자 공개 답변 테스트").wait_for()
    student.close()
    prof.close()


def test_survey_trash_restore_and_purge_ui(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/surveys/edit/new")
    prof.page.fill(".title-input", "휴지통 시험 설문")
    prof.page.get_by_role("button", name="+ 문항 추가").click()
    prof.page.fill(".q-title", "테스트 문항")
    prof.page.get_by_role("button", name="초안 저장").click()
    prof.page.wait_for_url(re.compile(r".*/surveys/edit/\d+$"))
    prof.go("/surveys")
    card = prof.page.locator(".card").filter(has_text="휴지통 시험 설문")
    for action in ("trash", "restore", "trash"):
        card.get_by_role("button", name="복원" if action == "restore" else "휴지통으로", exact=True).click()
        prof.page.locator(".modal").get_by_role("button", name="확인", exact=True).click()
        prof.page.get_by_role("button", name="설문 목록" if action == "restore" else "휴지통", exact=True).click()
        card.wait_for()
    prof.shot("survey_trash")
    card.get_by_role("button", name="영구 삭제").click()
    prof.page.locator(".modal input").fill("영구 삭제")
    prof.page.locator(".modal").get_by_role("button", name="확인", exact=True).click()
    card.wait_for(state="hidden")
    prof.close()


def test_consultation_download_and_print_view(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    prof.go("/staff/insights")
    panel = prof.page.locator(".export-panel")
    panel.locator("summary").click()
    panel.locator('input[type="date"]').nth(0).fill(SLOT_DAY.isoformat())
    panel.locator('input[type="date"]').nth(1).fill(SLOT_DAY.isoformat())
    prof.shot("consultation_export_options")
    with prof.page.expect_download() as event:
        panel.get_by_role("link", name="Excel 다운로드").click()
    assert event.value.suggested_filename.endswith(".xlsx")
    with prof.page.expect_popup() as popup:
        panel.get_by_role("link", name="PDF 저장 / 인쇄").click()
    print_page = popup.value
    print_page.wait_for_load_state("domcontentloaded")
    assert print_page.get_by_role("heading", name="ClassBridge 상담 자료").count(), (
        print_page.url, print_page.locator("body").inner_text())
    assert print_page.get_by_role("button", name="PDF 저장 / 인쇄").is_visible()
    assert "교수자 전용 상담 기록" not in print_page.locator("body").inner_text()
    print_page.screenshot(path=str(SHOTS / "consultation_print.png"), full_page=True)
    print_page.close()
    prof.close()


def test_developer_support_private_conversation_and_menu(server, browser):
    base, _ = server
    student = Session(browser, base, "support-student@test.ac.kr", MOBILE)
    student.go("/booking")
    student.page.get_by_role("button", name="더보기 메뉴").click()
    student.page.locator("#nav").get_by_role("link", name="도움말 · 문의").click()
    student.page.get_by_role("link", name="문의 작성", exact=True).click()
    student.page.get_by_text("#/booking", exact=True).wait_for()
    student.page.get_by_label("제목", exact=True).fill("모바일 화면 문의")
    student.page.get_by_label("내용", exact=True).fill("<img src=x onerror=alert(1)> 화면 문제 설명")
    student.shot("support_mobile_compose")
    student.page.get_by_role("button", name="문의 보내기", exact=True).click()
    student.page.wait_for_url(re.compile(r".*/help/tickets/\d+$"))
    ticket_id = student.page.url.rsplit("/", 1)[-1]
    student.page.get_by_text("<img src=x onerror=alert(1)> 화면 문제 설명", exact=True).wait_for()
    assert student.page.locator(".support-thread img").count() == 0
    dev = Session(browser, base, "admin@test.ac.kr", PC)
    assert dev.page.locator("#nav").get_by_role("link", name="도움말 · 문의").is_visible() is False
    dev.page.locator("#userbox").get_by_role("link", name="도움말 · 문의").click()
    dev.page.get_by_text("미확인 1건", exact=True).wait_for()
    dev.page.get_by_role("link", name="개발자 문의함", exact=True).click()
    dev.page.get_by_role("link", name="모바일 화면 문의", exact=True).click()
    dev.page.get_by_text("작성자: support-student (support-student@test.ac.kr)", exact=True).wait_for()
    dev.page.get_by_label("개발자 답변", exact=True).fill("화면 문제를 확인했습니다.")
    dev.page.get_by_role("button", name="답변 보내기", exact=True).click()
    dev.page.get_by_text("화면 문제를 확인했습니다.", exact=True).wait_for()
    dev.page.get_by_label("처리 상태", exact=True).select_option("completed")
    dev.page.get_by_role("button", name="상태 저장", exact=True).click()
    dev.page.locator(".badge.completed").wait_for()
    dev.shot("support_developer_reply")
    student.go("/help/mine")
    student.page.get_by_text("새 답변·변경", exact=True).wait_for()
    student.page.get_by_role("link", name="모바일 화면 문의", exact=True).click()
    student.page.get_by_text("화면 문제를 확인했습니다.", exact=True).wait_for()
    student.shot("support_mobile_reply")
    student.page.get_by_label("추가 내용", exact=True).fill("추가 질문이 있습니다.")
    student.page.get_by_role("button", name="추가 내용 보내기", exact=True).click()
    student.page.get_by_text("추가 질문이 있습니다.", exact=True).wait_for()
    student.page.locator(".badge.received").wait_for()
    professor = Session(browser, base, "prof@test.ac.kr", PC)
    professor.go("/help")
    assert professor.page.get_by_role("link", name="개발자 문의함", exact=True).count() == 0
    professor.go(f"/help/tickets/{ticket_id}")
    professor.page.get_by_text("문의를 찾을 수 없습니다", exact=True).wait_for()
    # Expected 404 deliberately tested above; don't count that console response as a runtime regression.
    professor.errors = [err for err in professor.errors if "404" not in err]
    professor.close()
    dev.close()
    student.close()


def test_mobile_available_slot_counts_in_staff_views(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE, service_workers="block")
    day = today_kst(utcnow()).isoformat()
    slots = [{"id": 9000 + i, "start_at": f"{day}T10:{i * 5:02d}:00+09:00",
              "end_at": f"{day}T11:00:00+09:00", "kind": "individual", "capacity": 1,
              "remaining": 1 if i < 2 or i > 3 else 0, "status": "cancelled" if i == 4 else "open",
              "bookable": i < 2, "mine": False, "location": "m205", "note": "",
              "reason": "" if i < 2 else "마감"} for i in range(6)]
    prof.page.route("**/api/slots?*", lambda route: route.fulfill(json=slots))
    prof.page.reload()
    prof.go("/slots")
    chip = prof.page.get_by_role("tab", name=re.compile("예약 가능 2건"))
    chip.wait_for()
    assert chip.locator("em").inner_text() == "2"
    slots[3].update(kind="group", capacity=3)
    bookings = [{"id": 8000 + i, "slot": slots[slot], "student_name": "검증 학생",
                 "student_id": 8100 + i, "student_email": "synthetic@test.ac.kr", "topic": "",
                 "consultation_type": "other", "consultation_mode": "in_person", "status": status}
                for i, (slot, status) in enumerate([(2, "booked"), (3, "booked"), (3, "booked"),
                    (3, "booked"), (0, "cancelled"), (1, "completed")])]
    prof.page.route("**/api/bookings?*", lambda route: route.fulfill(json=bookings))
    prof.go("/bookings")
    prof.page.get_by_role("button", name="주간 예약 시간표").click()
    chip = prof.page.get_by_role("tab", name=re.compile("예약 4명"))
    chip.wait_for()
    assert chip.locator("em").inner_text() == "4명"
    prof.shot("mobile_reserved_student_counts")
    prof.page.set_viewport_size(PC)
    prof.page.get_by_text("예약 4명", exact=True).wait_for()
    prof.page.set_viewport_size(MOBILE)
    # A cancellation releases one time; reloading must show the new count.
    slots[2].update(bookable=True, remaining=1, reason="")
    prof.go("/slots")
    prof.page.get_by_role("tab", name=re.compile("예약 가능 3건")).wait_for()
    prof.close()


def test_site_qr_available_to_guests_students_and_staff(server, browser):
    base, _ = server
    sessions = [Session(browser, base, email, MOBILE) for email in
                ("site-qr@test.ac.kr", "prof@test.ac.kr", "admin@test.ac.kr")]
    for session in sessions:
        session.go("/help")
        session.ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
        session.page.get_by_role("button", name="사이트 링크 복사").click()
        assert session.page.evaluate("navigator.clipboard.readText()") == base + "/"
        session.page.get_by_role("button", name="사이트 접속 QR", exact=True).click()
        image = session.page.get_by_alt_text("ClassBridge 사이트 접속 QR 코드")
        image.evaluate("img => img.decode()")
        with session.page.expect_download() as download:
            session.page.get_by_role("link", name="QR 이미지 저장(PNG)", exact=True).click()
        assert download.value.suggested_filename == "classbridge-site-qr.png"
        assert session.page.evaluate("document.documentElement.scrollWidth") <= MOBILE["width"] + 1
        session.shot("mobile_site_qr")
        session.close()
    context = browser.new_context(viewport=MOBILE)
    page = context.new_page()
    page.goto(base)
    page.get_by_role("button", name="사이트 접속 QR", exact=True).click()
    page.get_by_alt_text("ClassBridge 사이트 접속 QR 코드").evaluate("img => img.decode()")
    context.close()


def test_daytime_input_parser_boundaries(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", PC)
    result = prof.page.evaluate("""async () => {
      const m = await import('/static/js/schedule-input.js');
      const safe = fn => { try { return fn(); } catch { return 'invalid'; } };
      return {
        times: ['10 00', '1000', '10시', '3', '3 30', '12', '18:00', '7', '오전 6시', '저녁7시', '18:30', '10:60']
          .map(v => safe(() => m.parseTime(v))),
        dates: ['11 20', '11/20', '11월 20일', '1120', '20261120', '2/30', '1/1']
          .map(v => safe(() => m.parseDate(v, '2026-11-06'))),
        sentence: m.parseSchedule('11월 20일 3시~6시', '2026-11-06'),
        backwards: safe(() => m.parseSchedule('11월 20일 6시~3시', '2026-11-06')),
        leap: m.parseDate('2028-02-29', '2026-11-06'),
      };
    }""")
    assert result['times'] == ['10:00', '10:00', '10:00', '15:00', '15:30', '12:00', '18:00'] + ['invalid'] * 5
    assert result['dates'] == ['2026-11-20'] * 5 + ['invalid'] * 2
    assert result['sentence'] == {'date': '2026-11-20', 'start': '15:00', 'end': '18:00'}
    assert result['backwards'] == 'invalid' and result['leap'] == '2028-02-29'
    prof.close()


def test_simple_weekly_schedule_preview_summary_and_delete(server, browser):
    base, _ = server
    prof = Session(browser, base, "prof@test.ac.kr", MOBILE)
    prof.go('/slots')
    assert prof.page.locator('#nav a .nav-icon').count() >= 5
    prof.page.get_by_role('link', name='상담 등록', exact=True).click()
    day = today_kst(utcnow()) + timedelta(days=10)
    prof.page.get_by_label('한 문장으로 입력', exact=True).fill(f'{day.isoformat()} 3시~6시')
    prof.page.get_by_role('button', name='입력 내용 적용', exact=True).click()
    assert prof.page.get_by_label('시작', exact=True).input_value() == '15:00'
    assert prof.page.get_by_label('종료', exact=True).input_value() == '18:00'
    prof.page.get_by_label('반복 방식', exact=True).select_option('weekly')
    prof.page.get_by_label('총 몇 주', exact=True).fill('2')
    prof.page.get_by_role('button', name='등록 미리보기', exact=True).click()
    prof.page.get_by_text('생성할 새 상담 12건', exact=True).wait_for()
    preview = prof.page.get_by_role('region', name='등록 예정 달력')
    assert preview.get_by_role('button', name=f'{day.isoformat()} · 6개 예정', exact=True).count() == 1
    assert preview.locator('.preview-times li').count() == 6
    assert prof.page.evaluate('document.documentElement.scrollWidth') <= MOBILE['width'] + 1
    prof.page.set_viewport_size(PC)
    assert prof.page.evaluate('document.documentElement.scrollWidth') <= PC['width'] + 1
    prof.shot('pc_schedule_calendar_preview')
    prof.page.set_viewport_size(MOBILE)
    prof.shot('mobile_schedule_preview')
    prof.page.get_by_role('button', name='등록 확정', exact=True).click()
    prof.toast('12개 등록')
    prof.page.locator('.daily-title:focus').wait_for()
    assert prof.page.locator('#slot-create-panel').count() == 0
    assert prof.page.locator('.daily .card.slot.open').count() == 6
    summary = prof.page.get_by_role('region', name='예약 가능한 상담 일정')
    # More than three dates may already exist from other end-to-end scenarios.
    if summary.get_by_role('button', name='전체 일정 보기', exact=True).count():
        summary.get_by_role('button', name='전체 일정 보기', exact=True).click()
    summary.get_by_role('button', name=re.compile(f'{day.month}월 {day.day}일.*6개 시간')).click()
    prof.page.locator('.card.slot.open').first.click()
    prof.page.get_by_role('button', name='이 시간 취소', exact=True).click()
    prof.page.get_by_role('button', name='취소하기', exact=True).click()
    prof.toast('취소했습니다')
    prof.page.get_by_label('취소된 상담 시간 보기', exact=True).check()
    cancelled = prof.page.locator('.card.slot.cancelled').first
    cancelled.wait_for()
    cancelled.click()
    prof.page.get_by_role('button', name='삭제', exact=True).click()
    prof.toast('빈 상담 시간을 삭제했습니다')
    assert prof.page.locator('.card.slot.cancelled').count() == 0
    assert prof.page.evaluate('document.documentElement.scrollWidth') <= MOBILE['width'] + 1
    prof.shot('mobile_schedule_summary')
    prof.close()


def test_late_calendar_response_does_not_overwrite_new_page(server, browser):
    base, _ = server
    student = Session(browser, base, "slow-calendar@test.ac.kr", MOBILE)
    student.go('/booking')
    student.page.evaluate("""() => {
      const original = window.fetch.bind(window);
      window.releaseCalendar = [];
      window.holdCalendar = true;
      window.fetch = async (...args) => {
        const response = await original(...args);
        if (window.holdCalendar && String(args[0]).startsWith('/api/slots?')) {
          document.body.dataset.calendarHeld = 'true';
          return new Promise(resolve => window.releaseCalendar.push(() => resolve(response)));
        }
        return response;
      };
      window.oldCalendarRender = import('/static/js/views/student-booking.js')
        .then(module => module.render(document.getElementById('view')));
    }""")
    student.page.wait_for_selector('body[data-calendar-held="true"]')
    student.go('/my-bookings')
    student.page.evaluate("""async () => {
      window.holdCalendar = false;
      window.releaseCalendar.forEach(release => release());
      await window.oldCalendarRender;
    }""")
    assert student.page.get_by_role('heading', name='내 예약', exact=True).is_visible()
    assert student.page.get_by_role('region', name='예약 가능한 상담 일정').count() == 0
    student.close()


@pytest.mark.parametrize("viewport", [MOBILE, PC], ids=["mobile", "pc"])
def test_preview_month_boundary_and_professor_notification_summary(server, browser, viewport):
    base, _ = server
    session = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    page = session.page
    page.route("**/api/admin/notification-summary", lambda route: route.fulfill(json={
        "gmail": {"enabled": True, "recipient": True, "attention": 2, "pending": 1, "last_success": None},
        "push": {"enabled": False, "recipient": True, "attention": 0, "pending": 0,
                 "last_success": None, "session_registered": False}}))
    session.go("/bookings")
    assert page.get_by_role("region", name="내 예약 알림 상태").count() == 0
    session.go("/personal")
    panel = page.get_by_role("region", name="내 예약 알림 상태")
    panel.get_by_text("확인 필요 2건", exact=False).wait_for()
    assert "미설정" in panel.inner_text()
    session.shot("mobile_professor_notification_summary")
    page.route("**/api/admin/notification-summary", lambda route: route.fulfill(status=503, json={"message": "test"}))
    panel.get_by_role("button", name="상태 새로고침").click()
    panel.get_by_text("상태를 불러오지 못했습니다.", exact=False).wait_for()
    expected_error = "Failed to load resource: the server responded with a status of 503 (Service Unavailable)"
    assert session.errors == [expected_error]
    session.errors.remove(expected_error)
    page.evaluate("""async () => {
        const {schedulePreview} = await import('/static/js/components/schedule-preview.js');
        const root = document.createElement('div'); root.id='boundary-test';
        root.append(schedulePreview(['2030-12-31','2031-01-07'].map(d => ({
            start_at:d+'T10:00:00+09:00',end_at:d+'T10:30:00+09:00'}))));
        document.body.append(root);
    }""")
    preview = page.locator("#boundary-test")
    preview.get_by_role("button", name="다음 달").click()
    assert preview.get_by_role("button", name="2031-01-07 · 1개 예정").get_attribute("aria-pressed") == "true"
    assert "10:00 ~ 10:30" in preview.inner_text()
    preview.get_by_role("button", name="이전 달").click()
    assert preview.get_by_role("button", name="2030-12-31 · 1개 예정").get_attribute("aria-pressed") == "true"
    session.close()


def test_staff_personal_alerts_mobile(server, browser):
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", MOBILE)
    staff.page.get_by_role("button", name="더보기 메뉴").click()
    staff.page.locator("#nav").get_by_role("link", name="개인 설정").click()
    staff.page.get_by_role("heading", name="내 알림", exact=True).wait_for()
    daily = staff.page.get_by_label("평일 상담 요약 받기")
    reminder = staff.page.get_by_label("상담 30분 전 알림")
    at = staff.page.get_by_label("받을 시각 (한국시간)")
    assert daily.is_checked() and not reminder.is_checked() and at.input_value() == "10:00"
    reminder.check()
    at.fill("09:15")
    staff.page.get_by_role("button", name="저장", exact=True).click()
    staff.toast("저장했습니다")
    staff.page.reload()
    assert at.input_value() == "09:15" and reminder.is_checked()
    staff.close()


def test_guest_opens_writer_from_login(server, browser):
    base, _ = server
    ctx = browser.new_context(viewport=MOBILE)
    page = ctx.new_page()
    page.goto(base)
    assert not page.get_by_label("이 기기에서 30일간 로그인 유지").is_checked()
    page.get_by_role("link", name="로그인 없이 익명 건의하기").click()
    assert page.get_by_label("공개 범위").input_value() == "private"
    page.locator("textarea").fill("로그인 없는 접수 확인")
    page.get_by_role("button", name="익명으로 제출").click()
    page.get_by_text("건의가 익명으로 접수되었습니다").wait_for()
    ctx.close()


def test_mobile_booking_summary(server, browser):
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", MOBILE)
    page = staff.page
    page.clock.install(time="2026-11-10T09:00:00+09:00")
    booking = {"id": 214, "slot": {"id": 7, "start_at": "2026-11-10T10:00:00+09:00", "kind": "individual"},
               "applicant_name": "예약 학생", "student_number": "20260001", "student_email": "example@test.ac.kr",
               "status": "booked", "topic": "상담 주제"}
    page.route("**/api/bookings?*", lambda r: r.fulfill(json=[booking]))
    staff.go("/bookings")
    card = page.locator("details[data-booking-id='214']")
    summary = card.locator(":scope > summary")
    assert "예약 학생 · 20260001" in summary.inner_text()
    assert "1시간 후" in summary.inner_text()
    assert "상담 주제" not in card.inner_text()
    summary.click()
    assert card.get_by_text("상담 주제", exact=True).is_visible()
    assert card.get_by_role("button", name="일정 조정").is_visible()
    summary.click()
    page.clock.fast_forward(3600000)
    assert " 후" not in summary.inner_text()
    staff.close()


@pytest.mark.parametrize("viewport", [PC, MOBILE])
def test_unresolved_history_filter_includes_past_and_allows_staff_correction(server, browser, viewport):
    base, _ = server
    staff = Session(browser, base, "prof@test.ac.kr", viewport, service_workers="block")
    page = staff.page
    requests = []
    booking = {"id": 987654, "status": "expired", "student_name": "History fixture",
               "student_email": "fixture@example.test", "topic": "", "professor_note": "",
               "slot": {"start_at": "2026-01-01T01:00:00Z", "end_at": "2026-01-01T01:30:00Z",
                        "kind": "individual"}}

    def bookings(route):
        requests.append(route.request.url)
        route.fulfill(json=[booking] if "status=expired" in route.request.url else [])

    page.route("**/api/bookings?*", bookings)
    staff.go("/bookings")
    page.get_by_role("button", name="예약 목록", exact=True).click()
    page.get_by_label("예약 상태", exact=True).select_option("expired")
    page.locator(".badge.expired").wait_for(state="attached")
    assert "from_date=" not in requests[-1]
    assert page.get_by_text("과거 포함 · 결과 확인 필요 · 1건 (한국시간)", exact=True).count() == 1
    row = page.locator('[data-booking-id="987654"]')
    if viewport == MOBILE:
        row.locator("summary").first.click()
    row.locator("details.action-more summary").click()
    assert row.get_by_role("button", name="완료", exact=True).is_visible()
    assert row.get_by_role("button", name="미참석", exact=True).is_visible()
    staff.close()
