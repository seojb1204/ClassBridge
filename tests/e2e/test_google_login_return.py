"""Real browser + real worker/cookies; Google exchange is a one-use test verifier."""
import os
import socket
import threading
from urllib.parse import parse_qs, urlparse

import pytest
import uvicorn

from app.core.errors import Unauthorized
from app.core.identity import VerifiedIdentity
from app.db import Base
from app.main import create_app
from tests.conftest import make_settings
from tests.e2e.test_e2e import MOBILE, PC, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not os.getenv('RUN_E2E'), reason='RUN_E2E not set')


@pytest.mark.parametrize('viewport', [PC, MOBILE])
def test_oauth_return_with_active_worker_exchanges_code_once(tmp_path, browser, viewport):  # noqa: F811
    attempts = []
    def verifier(settings, code, nonce):
        attempts.append(code)
        if len(attempts) > 1:
            raise Unauthorized('one-time code already consumed')
        return VerifiedIdentity('browser-oauth', 'oauth-browser@test.ac.kr', True, '로그인 검증')
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    base = f'http://127.0.0.1:{sock.getsockname()[1]}'
    app = create_app(make_settings(f'sqlite:///{tmp_path}/oauth.db', base_url=base,
                                  google_client_id='test-client', google_client_secret='test-secret'),
                     identity_verifier=verifier)
    Base.metadata.create_all(app.state.engine)
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    context = browser.new_context(viewport=viewport, service_workers='allow')
    try:
        page = context.new_page()
        page.goto(base + '/')
        page.evaluate('navigator.serviceWorker.ready.then(() => true)')
        page.reload()
        assert page.evaluate('Boolean(navigator.serviceWorker.controller)')
        login = context.request.get(base + '/auth/google/login', max_redirects=0)
        state = parse_qs(urlparse(login.headers['location']).query)['state'][0]
        page.goto(base + '/auth/google/callback?code=once&state=' + state)
        page.wait_for_url(base + '/#/booking')
        page.wait_for_selector('body[data-ready="/booking"]')
        assert context.request.get(base + '/api/me').json()['email'] == 'oauth-browser@test.ac.kr'
        page.reload()
        page.wait_for_selector('body[data-ready="/booking"]')
        assert attempts == ['once']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    finally:
        context.close()
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        app.state.engine.dispose()
