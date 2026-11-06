"""앱 조립만 담당한다. 업무 로직은 services/, HTTP 처리는 routers/에 있다."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import Settings, load_settings
from app.core.errors import AppError
from app.core.middleware import install_log_filter, install_security_headers
from app.core.rate_limit import RateLimiter
from app.db import make_engine, make_sessionmaker
from app.infra.ai_client import build_ai_client
from app.infra.google_oauth import verify_with_google
from app.routers import (
    admin,
    analysis,
    announcement,
    auth,
    bookings,
    exports,
    public_surveys,
    site_share,
    suggestions,
    support,
    surveys,
)
from app.services.notifications import NotificationWorker

log = logging.getLogger("classbridge")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def create_app(settings: Settings | None = None, identity_verifier=None) -> FastAPI:
    settings = settings or load_settings()
    settings.validate()
    @asynccontextmanager
    async def lifespan(app):
        worker = None
        if settings.gmail_notifications_enabled or settings.push_enabled:
            worker = NotificationWorker(app.state.SessionLocal, settings)
            worker.start()
        try:
            yield
        finally:
            if worker:
                await asyncio.to_thread(worker.stop)

    app = FastAPI(lifespan=lifespan, title="ClassBridge", version="1.0.0",
                  docs_url=None if settings.is_production else "/docs", redoc_url=None)
    engine = make_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.SessionLocal = make_sessionmaker(engine)
    app.state.SessionLocal.configure(info={"settings": settings})
    app.state.identity_verifier = identity_verifier or verify_with_google
    # 건의함: 제출 '횟수'는 무제한이지만 자동화된 폭주는 차단 (분당 5회, 시간당 30회)
    app.state.suggestion_limiter = RateLimiter([(5, 60), (30, 3600)])
    app.state.support_limiter = RateLimiter([(10, 60), (60, 3600)])
    app.state.public_survey_limiter = RateLimiter([(5, 60), (30, 3600)])
    app.state.ai_limiter = RateLimiter([(10, 3600)])
    app.state.ai_client = build_ai_client(settings)

    install_security_headers(app, hsts=settings.is_production)
    install_log_filter()

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        # 입력값 원문은 응답·로그에 되돌려주지 않는다 (익명 본문 노출 방지)
        fields = [".".join(str(x) for x in e.get("loc", [])[1:]) for e in exc.errors()]
        return JSONResponse({"error": "validation", "message": "입력값을 확인하세요", "fields": fields},
                            status_code=422)

    @app.exception_handler(OperationalError)
    async def _db_down(_: Request, exc: OperationalError):
        log.error("database error: %s", type(exc.orig).__name__)
        return JSONResponse({"error": "db_unavailable",
                             "message": "일시적으로 데이터베이스에 연결할 수 없습니다. 잠시 후 다시 시도하세요"},
                            status_code=503)

    for r in (auth.router, admin.router, bookings.router, exports.router, surveys.router,
              suggestions.router, support.router, analysis.router, announcement.router, public_surveys.router):
        app.include_router(r)
    app.include_router(site_share.router)
    from app.routers import notifications
    app.include_router(notifications.router)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {"status": "ok"}
        except OperationalError:
            return JSONResponse({"status": "db_unavailable"}, status_code=503)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/sw.js", include_in_schema=False)
        def service_worker():
            return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript",
                                headers={"Cache-Control": "no-cache, must-revalidate",
                                         "Service-Worker-Allowed": "/"})

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(STATIC_DIR / "index.html")

    return app
