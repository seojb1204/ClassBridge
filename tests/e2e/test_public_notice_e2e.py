import os
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from tests.e2e.test_e2e import ROOT, SHOTS, _free_port
from tests.e2e.test_e2e import browser as notice_browser  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv("RUN_E2E"), reason="RUN_E2E not set")


def test_mobile_public_notice_and_required_consents(tmp_path, notice_browser):  # noqa: F811
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "APP_ENV": "test", "DATABASE_URL": f"sqlite:///{tmp_path}/notice.db",
           "PUBLIC_NOTICE_ENABLED": "true", "OPERATOR_NAME": "시험 운영자",
           "OPERATOR_AFFILIATION": "시험 대학", "SUPPORT_EMAIL": "help@example.invalid",
           "GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "test-secret",
           "DEV_LOGIN_ENABLED": "false"}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env,
                   check=True, capture_output=True)
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:create_app", "--factory",
                                "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
                               cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    context = notice_browser.new_context(viewport={"width": 390, "height": 844}, locale="ko-KR")
    try:
        for _ in range(60):
            try:
                if httpx.get(base + "/healthz", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            pytest.fail("Local notice server did not start")
        page = context.new_page()
        page.goto(base)
        button = page.get_by_role("button", name="Google 계정으로 로그인")
        button.wait_for()
        button.click()
        assert urlparse(page.url).path == "/"
        page.locator('input[name="notice_ack"]').check()
        button.click()
        assert urlparse(page.url).path == "/"
        SHOTS.mkdir(exist_ok=True, parents=True)
        page.screenshot(path=str(SHOTS / "public-notice-mobile.png"), full_page=True)
        page.locator('input[name="transfer_ack"]').check()
        # Exercise local server validation/redirect, without transmitting to Google.
        def check_redirect(route):
            response = route.fetch(max_redirects=0)
            assert response.status == 302
            assert urlparse(response.headers["location"]).hostname == "accounts.google.com"
            route.fulfill(status=200, content_type="text/html", body="<p>OAuth redirect verified</p>")

        page.route(base + "/auth/google/login*", check_redirect)
        with page.expect_request(lambda r: urlparse(r.url).path == "/auth/google/login") as req:
            button.click()
        query = parse_qs(urlparse(req.value.url).query)
        assert query["notice_ack"] == query["transfer_ack"] == ["yes"]
        page.get_by_text("OAuth redirect verified").wait_for()
        page.goto(base + "/privacy")
        assert page.get_by_role("heading", name="ClassBridge 이용·개인정보 안내").is_visible()
        assert page.locator("body").evaluate("el => el.scrollWidth <= window.innerWidth")
        page.screenshot(path=str(SHOTS / "privacy-mobile.png"), full_page=True)
    finally:
        context.close()
        process.terminate()
        process.wait(timeout=10)
