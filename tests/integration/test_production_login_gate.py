"""Security invariant: production never offers passwordless development login."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import ConfigError, Settings
from app.main import create_app


def _settings():
    return Settings(
        env="production",
        staging_mode=True,
        staging_allowed_emails=["admin@test.ac.kr"],
        admin_emails=["admin@test.ac.kr"],
        database_url="postgresql+psycopg://localhost/classbridge_nonexistent",
        secret_key="secure-only-for-test-credentials-1234567890",
        cookie_secure=True,
        dev_login_enabled=False,
    )


def test_production_dev_login_endpoint_is_disabled_even_with_staging():
    app = create_app(_settings())
    try:
        client = TestClient(app)
        config = client.get("/api/auth/config")
        assert config.status_code == 200
        assert config.json()["dev_login"] is False
        login = client.post("/auth/dev/login", json={"email": "admin@test.ac.kr"})
        assert login.status_code == 404
    finally:
        app.state.engine.dispose()


def test_production_rejects_attempt_to_enable_dev_login():
    settings = _settings()
    settings.dev_login_enabled = True
    with pytest.raises(ConfigError, match="DEV_LOGIN_ENABLED"):
        settings.validate()
