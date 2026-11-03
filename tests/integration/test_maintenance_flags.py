"""Prelaunch feature gates must reject accidental student submissions."""
from __future__ import annotations

from sqlalchemy import func, select

from app.models import Suggestion, Survey
from tests.conftest import build_app, login


def test_disabled_anonymous_features_fail_closed_for_every_role(tmp_path):
    app = build_app(f"sqlite:///{tmp_path}/locked.db",
                    feature_surveys=False, feature_suggestions=False, ai_mode="disabled")
    try:
        for email in ("s1@test.ac.kr", "prof@test.ac.kr", "admin@test.ac.kr"):
            client = login(app, email)
            assert client.get("/api/surveys/student/list").status_code == 503
            assert client.get("/api/surveys").status_code == 503
            assert client.get("/api/suggestions").status_code == 503
            assert client.post("/api/suggestions", json={
                "category": "other", "content": "should not be stored"}).status_code == 503
        db = app.state.SessionLocal()
        try:
            assert db.execute(select(func.count()).select_from(Suggestion)).scalar_one() == 0
            assert db.execute(select(func.count()).select_from(Survey)).scalar_one() == 0
        finally:
            db.close()
    finally:
        app.state.engine.dispose()
