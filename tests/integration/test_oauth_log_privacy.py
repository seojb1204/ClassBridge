import logging

import httpx
import pytest

from app.core.errors import Unauthorized
from app.core.middleware import AnonymousAccessLogFilter
from app.infra.google_oauth import verify_with_google
from tests.conftest import make_settings


def test_callback_access_log_strips_query_only():
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s %s %s %s %s',
        ('client', 'GET', '/auth/google/callback?code=secret&state=private', '1.1', 200), None)
    assert AnonymousAccessLogFilter().filter(record)
    assert record.args[2] == '/auth/google/callback'
    assert 'secret' not in record.getMessage() and 'private' not in record.getMessage()


@pytest.mark.parametrize('error,expected', [('invalid_grant', 'invalid_grant'), ('SECRET', 'other')])
def test_token_error_log_uses_fixed_categories(monkeypatch, caplog, error, expected):
    # Alembic fileConfig in earlier migration tests disables existing loggers.
    monkeypatch.setattr(logging.getLogger("classbridge.oauth"), "disabled", False)
    monkeypatch.setattr(httpx, 'post', lambda *args, **kwargs: httpx.Response(400,
        json={'error': error, 'error_description': 'PRIVATE description'}))
    with caplog.at_level(logging.WARNING), pytest.raises(Unauthorized):
        verify_with_google(make_settings('sqlite://', google_client_id='cid', google_client_secret='SECRET'),
                           'PRIVATE-code', 'PRIVATE-nonce')
    assert f'category={expected}' in caplog.text
    assert 'SECRET' not in caplog.text and 'PRIVATE' not in caplog.text
