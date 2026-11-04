"""Fail closed before connecting to a restore target; never print credentials."""
from __future__ import annotations

import os
import sys
from urllib.parse import parse_qsl, unquote, urlsplit


def identity(uri: str) -> tuple[str, str]:
    try:
        parts = urlsplit(uri)
        host = parts.hostname
        database = unquote(parts.path.removeprefix("/"))
        # libpq connection overrides could bypass the hostname/database checks.
        query = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
        if (parts.scheme not in {"postgres", "postgresql"} or not host or not database
                or parts.fragment or "/" in database or "," in host
                or any(key not in {"sslmode", "connect_timeout", "application_name"}
                       for key, _ in query)):
            raise ValueError
        _ = parts.port
        if any(char.isspace() for char in host + database):
            raise ValueError
        return host.lower(), database
    except ValueError:
        raise ValueError("Use a PostgreSQL URI without connection override parameters") from None


def validate(env: dict[str, str]) -> None:
    required = ("DATABASE_URL_DIRECT", "RESTORE_DATABASE_URL",
                "EXPECTED_RESTORE_HOST", "EXPECTED_RESTORE_DATABASE")
    if any(not env.get(key, "").strip() for key in required):
        raise ValueError("Source URI and explicitly approved restore host/database are required")
    source_host, _ = identity(env["DATABASE_URL_DIRECT"])
    target_host, target_database = identity(env["RESTORE_DATABASE_URL"])
    expected = (env["EXPECTED_RESTORE_HOST"].lower(), env["EXPECTED_RESTORE_DATABASE"])
    if (target_host, target_database) != expected:
        raise ValueError("Restore destination does not match the approved host/database")
    if not target_database.startswith("classbridge_restore_"):
        raise ValueError("Restore database name must start with classbridge_restore_")
    # A separate database on the source endpoint is not sufficient isolation.
    if source_host.replace("-pooler.", ".") == target_host.replace("-pooler.", "."):
        raise ValueError("Restore requires a separate host from the source database")
    if "-pooler." in target_host or "-pooler." in source_host:
        raise ValueError("Backup and restore require direct connections")


if __name__ == "__main__":
    try:
        validate(dict(os.environ))
    except ValueError as exc:
        print(f"Restore refused: {exc}", file=sys.stderr)
        sys.exit(2)
