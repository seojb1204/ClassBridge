from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models.support import SupportMessage, SupportTicket


def create(client, **overrides):
    body = {"category": "bug", "title": "오류 신고", "content": "문제 재현 방법", "page_path": "/booking"}
    r = client.post("/api/support/tickets", json={**body, **overrides})
    assert r.status_code == 201, r.text
    return f"/api/support/tickets/{r.json()['id']}"


def test_private_support_ownership_every_endpoint(app, clients):
    own, other, prof, admin = (clients[k] for k in ("s1", "s2", "prof", "admin"))
    path = create(own)
    anon = TestClient(app)
    for url in ("/api/support/counts", "/api/support/tickets", path):
        assert anon.get(url).status_code == 401
    for client in (other, prof):
        assert client.get(path).status_code == 404
        assert client.get("/api/support/tickets").json() == []
        assert client.get("/api/support/tickets?inbox=true").status_code == 403
        assert client.get(path + "?inbox=true").status_code == 403
        assert client.post(path + "/messages", json={"content": "intrude"}).status_code == 404
        assert client.post(path + "/messages?inbox=true", json={"content": "intrude"}).status_code == 403
        assert client.post(path + "/read", json={"updated_at": "2026-01-01T00:00:00Z"}).status_code == 404
        assert client.post(path + "/read?inbox=true", json={"updated_at": "2026-01-01T00:00:00Z"}).status_code == 403
        assert client.put(path + "/status", json={"status": "completed"}).status_code == 403
        assert client.get("/api/support/counts").json() == {"mine": 0, "inbox": 0}
    assert "owner" not in own.get(path).json()
    assert admin.get(path + "?inbox=true").json()["owner"]["email"] == "s1@test.ac.kr"
    prof_path = create(prof)
    assert prof.get(prof_path).status_code == 200
    assert len(admin.get("/api/support/tickets?inbox=true").json()) == 2


def test_support_conversation_status_and_unread_race(clients):
    own, dev = clients["s1"], clients["admin"]
    path = create(own)
    assert dev.get("/api/support/counts").json()["inbox"] == 1
    first = dev.get(path + "?inbox=true").json()
    assert own.post(path + "/messages", json={"content": "추가 내용"}).status_code == 201
    assert dev.post(path + "/read?inbox=true", json={"updated_at": first["updated_at"]}).status_code == 204
    assert dev.get("/api/support/counts").json()["inbox"] == 1  # newer message survives stale read
    current = dev.get(path + "?inbox=true").json()
    dev.post(path + "/read?inbox=true", json={"updated_at": current["updated_at"]})
    assert dev.get("/api/support/counts").json()["inbox"] == 0
    assert dev.post(path + "/messages?inbox=true", json={"content": "답변"}).status_code == 201
    detail = own.get(path).json()
    assert detail["status"] == "reviewing"
    assert [m["is_developer"] for m in detail["messages"]] == [False, False, True]
    assert own.get("/api/support/counts").json()["mine"] == 1
    assert dev.put(path + "/status", json={"status": "completed"}).status_code == 204
    own.post(path + "/read", json={"updated_at": detail["updated_at"]})
    assert own.get("/api/support/counts").json()["mine"] == 1  # newer status survives stale read
    detail = own.get(path).json()
    own.post(path + "/read", json={"updated_at": detail["updated_at"]})
    assert own.get("/api/support/counts").json()["mine"] == 0
    own.post(path + "/messages", json={"content": "추가 질문"})
    assert own.get(path).json()["status"] == "received"
    assert dev.get("/api/support/counts").json()["inbox"] == 1


def test_support_validates_content_path_csrf_and_limits(app, clients):
    c = clients["s1"]
    base = {"title": "test", "content": "hello", "category": "bug"}
    for invalid in ({"title": "  "}, {"content": "\x00 "}, {"content": "x" * 4001}, {"category": "other"},
                    {"title": "x" * 121}, {"page_path": "https://evil.test"}, {"page_path": "/booking?token=secret"}):
        assert c.post("/api/support/tickets", json={**base, **invalid}).status_code == 422
    assert c.post("/api/support/tickets", json=base, headers={"X-CSRF-Token": "wrong"}).status_code == 403
    path = create(c, title="x" * 120, content="x" * 4000)
    assert len(c.get(path).json()["messages"][0]["content"]) == 4000
    for _ in range(9):
        assert c.post(path + "/messages", json={"content": "repeat"}).status_code == 201
    assert c.post(path + "/messages", json={"content": "overflow"}).status_code == 429
    assert c.post("/api/support/tickets", json=base).status_code == 429
    with app.state.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SupportTicket)) == 1
        assert db.scalar(select(func.count()).select_from(SupportMessage)) == 10
