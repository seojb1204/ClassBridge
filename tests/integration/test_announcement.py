import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import AppSetting, AuditLog


def notice(revision=0, published=True, **kw):
    return {"title": "상담 안내", "body": "예약 전 준비해 주세요.\n질문을 정리해 오세요.",
            "published": published, "revision": revision, **kw}


def test_announcement_lifecycle_and_settings_isolation(app, clients):
    p, a, s = clients["prof"], clients["admin"], clients["s1"]
    before = a.get("/api/admin/settings").json()
    assert s.get("/api/announcement").json() == {"announcement": None}
    draft = p.put("/api/announcement", json=notice(published=False))
    assert draft.status_code == 200 and draft.json()["announcement"]["revision"] == 1
    assert s.get("/api/announcement").json() == {"announcement": None}
    assert a.get("/api/announcement").json()["announcement"]["title"] == "상담 안내"
    assert a.put("/api/announcement", json=notice(1)).status_code == 200
    visible = s.get("/api/announcement")
    assert visible.headers["Cache-Control"] == "no-store"
    assert set(visible.json()["announcement"]) == {"title", "body", "updated_at"}
    assert p.put("/api/announcement", json=notice(2, published=False)).status_code == 200
    assert s.get("/api/announcement").json()["announcement"] is None
    assert a.get("/api/admin/settings").json() == before
    assert p.put("/api/admin/settings", json={"booking_window_days": 5}).status_code == 403
    with app.state.SessionLocal() as db:
        logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "announcement.update")))
        assert len(logs) == 3
        assert all("body" not in row.detail and "title" not in row.detail for row in logs)


def test_announcement_permissions_and_csrf(app, clients):
    anon = TestClient(app)
    assert anon.get("/api/announcement").status_code == 401
    assert anon.put("/api/announcement", json=notice()).status_code == 401
    assert clients["s1"].put("/api/announcement", json=notice()).status_code == 403
    assert clients["prof"].put("/api/announcement", json=notice(), headers={"X-CSRF-Token": "bad"}).status_code == 403
    assert clients["prof"].get("/api/announcement").json()["announcement"]["revision"] == 0


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"body": "\n"}, {"title": "가" * 101}, {"body": "가" * 2001},
    {"revision": -1}, {"revision": True}, {"unexpected": "value"},
])
def test_announcement_invalid_input(clients, changes):
    assert clients["prof"].put("/api/announcement", json=notice(**changes)).status_code == 422


def test_announcement_stale_edit_preserves_newer_value(clients):
    p, a = clients["prof"], clients["admin"]
    assert p.put("/api/announcement", json=notice()).status_code == 200
    assert a.put("/api/announcement", json=notice()).status_code == 409
    assert a.put("/api/announcement", json=notice(1, title="새 공지")).status_code == 200
    assert p.put("/api/announcement", json=notice(1, title="오래된 편집")).status_code == 409
    assert p.get("/api/announcement").json()["announcement"]["title"] == "새 공지"


def test_announcement_audit_failure_rolls_back(app, clients, monkeypatch):
    from app.routers import announcement

    def fail(*args, **kwargs):
        raise RuntimeError("test failure")

    monkeypatch.setattr(announcement.audit, "add", fail)
    with pytest.raises(RuntimeError):
        clients["prof"].put("/api/announcement", json=notice())
    with app.state.SessionLocal() as db:
        assert db.get(AppSetting, announcement.KEY) is None
