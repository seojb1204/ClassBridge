"""보안 헤더와 익명 제출 경로의 접근 로그 억제."""
from __future__ import annotations

import logging
import re

from fastapi import FastAPI, Request

# 익명 제출 요청은 접근 로그(시각·IP·경로)에 남기지 않는다 → 로그와 응답의 시간 대조 방지
ANON_PATHS = re.compile(r"^/api/(surveys/\d+/responses|suggestions|public-surveys/[A-Za-z0-9_-]+(?:/responses)?)(\?.*)?$")


class AnonymousAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            method, path = str(args[1]), str(args[2])
            if ANON_PATHS.match(path) and (method == "POST" or path.startswith("/api/public-surveys/")):
                return False
        return True


def install_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, AnonymousAccessLogFilter) for f in logger.filters):
        logger.addFilter(AnonymousAccessLogFilter())


CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self' https://accounts.google.com"
)


def install_security_headers(app: FastAPI, hsts: bool) -> None:
    @app.middleware("http")
    async def _headers(request: Request, call_next):
        response = await call_next(request)
        h = response.headers
        h.setdefault("Content-Security-Policy", CSP)
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.url.path.startswith("/api/"):
            h.setdefault("Cache-Control", "no-store")
        elif request.url.path == "/" or (request.url.path.startswith("/static/")
                                        and request.url.path.endswith((".js", ".css", ".html"))):
            # Require a fresh asset version after each deploy; avoid stale JS/CSS.
            h.setdefault("Cache-Control", "no-cache, must-revalidate")
        if hsts:
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
