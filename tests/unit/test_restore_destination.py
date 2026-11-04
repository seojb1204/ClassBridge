from __future__ import annotations

import pytest

from scripts.validate_restore_target import identity, validate


def settings():
    return {
        "DATABASE_URL_DIRECT": "postgresql://user:dummy@source.example/neondb?sslmode=require",
        "RESTORE_DATABASE_URL": "postgresql://user:dummy@localhost:55432/classbridge_restore_trial",
        "EXPECTED_RESTORE_HOST": "localhost",
        "EXPECTED_RESTORE_DATABASE": "classbridge_restore_trial",
    }


def test_approved_isolated_destination():
    validate(settings())


@pytest.mark.parametrize("key,value", [
    ("EXPECTED_RESTORE_HOST", "other.example"),
    ("EXPECTED_RESTORE_DATABASE", "other_restore"),
    ("DATABASE_URL_DIRECT", "postgresql://localhost/neondb"),
    ("DATABASE_URL_DIRECT", "postgresql://source-pooler.example/neondb"),
    ("RESTORE_DATABASE_URL", "postgresql://localhost/classbridge_restore_trial?host=source.example"),
    ("RESTORE_DATABASE_URL", "postgresql://localhost/classbridge_restore_trial?options=-csearch_path=public"),
    ("RESTORE_DATABASE_URL", "postgresql://localhost/classbridge_restore_trial?dbname=neondb"),
    ("RESTORE_DATABASE_URL", "host=source.example dbname=neondb"),
])
def test_wrong_or_overridden_destination_is_refused(key, value):
    env = settings()
    env[key] = value
    with pytest.raises(ValueError):
        validate(env)


@pytest.mark.parametrize("key", list(settings()))
def test_missing_confirmation_is_refused(key):
    env = settings()
    del env[key]
    with pytest.raises(ValueError):
        validate(env)


def test_database_name_is_not_only_a_substring():
    env = settings()
    env["RESTORE_DATABASE_URL"] = "postgresql://localhost/production_restore"
    env["EXPECTED_RESTORE_DATABASE"] = "production_restore"
    with pytest.raises(ValueError, match="start with"):
        validate(env)


def test_connection_parse_error_never_includes_password():
    with pytest.raises(ValueError) as error:
        identity("postgresql://user:private-fixture@localhost:bad/db")
    assert "private-fixture" not in str(error.value)
