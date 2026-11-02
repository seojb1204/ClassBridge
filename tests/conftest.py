from __future__ import annotations

import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.db import Base, utcnow
from app.main import create_app
from app.timeutil import today_kst

ADMIN = "admin@test.ac.kr"
PROF = "prof@test.ac.kr"
PG_URL = os.getenv("TEST_PG_URL")  # 예: postgresql+psycopg://postgres@127.0.0.1:5433/classbridge_test


def make_settings(db_url: str, **kw) -> Settings:
    base = dict(env="test", database_url=db_url, dev_login_enabled=True,
                admin_emails=[ADMIN], professor_emails=[PROF], ai_mode="demo")
    base.update(kw)
    return Settings(**base)


def build_app(db_url: str, **kw):
    app = create_app(make_settings(db_url, **kw))
    Base.metadata.drop_all(app.state.engine)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def app(tmp_path):
    a = build_app(f"sqlite:///{tmp_path}/test.db")
    yield a
    a.state.engine.dispose()


def login(app, email: str, name: str = "") -> TestClient:
    c = TestClient(app)
    r = c.post("/auth/dev/login", json={"email": email, "name": name or email.split("@")[0]})
    assert r.status_code == 200, r.text
    me = c.get("/api/me").json()
    c.headers["X-CSRF-Token"] = me["csrf_token"]
    c.me = me  # type: ignore[attr-defined]
    return c


@pytest.fixture
def clients(app):
    """admin, prof, 학생 3명 클라이언트."""
    return {
        "admin": login(app, ADMIN, "관리자"),
        "prof": login(app, PROF, "교수"),
        "s1": login(app, "s1@test.ac.kr", "학생1"),
        "s2": login(app, "s2@test.ac.kr", "학생2"),
        "s3": login(app, "s3@test.ac.kr", "학생3"),
    }


def future_day(days: int = 2) -> date:
    return today_kst(utcnow()) + timedelta(days=days)


def make_slots(client, day: date | None = None, start="10:00", end="11:00", duration=30,
               kind="individual", capacity=1, **kw) -> list[int]:
    day = day or future_day()
    r = client.post("/api/slots", json={"start_date": day.isoformat(), "start_time": start, "end_time": end,
                                        "duration_minutes": duration, "kind": kind, "capacity": capacity, **kw})
    assert r.status_code == 201, r.text
    return r.json()["slot_ids"]
