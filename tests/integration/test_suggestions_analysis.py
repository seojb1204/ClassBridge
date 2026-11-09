from __future__ import annotations

from sqlalchemy import select

from app.models import Booking, Suggestion
from tests.conftest import make_slots


def test_submit_and_read(app, clients):
    s1, p = clients["s1"], clients["prof"]
    for i in range(3):
        assert s1.post("/api/suggestions", json={"category": "lecture", "content": f"의견 {i}"}).status_code == 201
    items = p.get("/api/suggestions").json()
    assert len(items) == 3 and set(items[0]) == {"id", "category", "content", "submitted_on", "status",
                                             "is_public", "deleted_on", "replies"}
    assert p.put(f"/api/suggestions/{items[0]['id']}/status", json={"status": "reviewed"}).json()["status"] == "reviewed"
    stats = p.get("/api/suggestions/stats").json()
    assert stats["total"] == 3 and stats["by_category"] == {"lecture": 3}


def test_no_author_stored(app, clients):
    clients["s1"].post("/api/suggestions", json={"category": "other", "content": "익명 테스트"})
    db = app.state.SessionLocal()
    row = db.execute(select(Suggestion)).scalar_one()
    db.close()
    assert not hasattr(row, "user_id") and not hasattr(row, "created_at")


def test_rate_limit_blocks_bursts_not_total(app, clients):
    s1, s2 = clients["s1"], clients["s2"]
    codes = [s1.post("/api/suggestions", json={"category": "other", "content": f"{i}"}).status_code for i in range(6)]
    assert codes == [201] * 5 + [429]
    # 다른 학생은 영향 없음
    assert s2.post("/api/suggestions", json={"category": "other", "content": "ok"}).status_code == 201


def test_content_validation(clients):
    s1 = clients["s1"]
    assert s1.post("/api/suggestions", json={"category": "other", "content": "   "}).status_code == 400
    assert s1.post("/api/suggestions", json={"category": "other", "content": "x" * 2001}).status_code == 400
    assert s1.post("/api/suggestions", json={"category": "hack", "content": "x"}).status_code == 422


def test_html_stored_as_text(clients):
    s1, p = clients["s1"], clients["prof"]
    payload = "<img src=x onerror=alert(1)>"
    s1.post("/api/suggestions", json={"category": "other", "content": payload})
    r = p.get("/api/suggestions")
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()[0]["content"] == payload  # 화면에서는 textContent로만 렌더링 (static/js/ui.js)


def test_local_analysis(clients):
    s1, s2, s3, p = clients["s1"], clients["s2"], clients["s3"], clients["prof"]
    s1.post("/api/suggestions", json={"category": "assignment", "content": "과제가 너무 많아요"})
    s2.post("/api/suggestions", json={"category": "assignment", "content": "과제 양을 줄여주세요"})
    s3.post("/api/suggestions", json={"category": "lecture", "content": "설명이 좋아요 감사합니다"})
    r = p.post("/api/analysis", json={"source": "suggestions"}).json()
    assert r["engine"] == "local-keyword" and r["total"] == 3
    assert r["classification"]["improvement"] == 2 and r["classification"]["positive"] == 1
    kw = {t["title"] for t in r["themes"]}
    assert "과제" in kw
    # 예시는 원문에서만 가져온다
    originals = {"과제가 너무 많아요", "과제 양을 줄여주세요", "설명이 좋아요 감사합니다"}
    assert all(ex in originals for t in r["themes"] for ex in t["examples"])


def test_consultation_notes_never_reach_analysis(app, clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    p.put(f"/api/bookings/{bid}/note", json={"note": "민감한상담기록"})
    sent = []

    class Spy:
        name = "external"

        def analyze(self, items):
            sent.extend(items)
            return {"summary": "", "themes": []}

    app.state.settings.ai_mode = "external"
    app.state.ai_client = Spy()
    s1.post("/api/suggestions", json={"category": "other", "content": "연락처 010-1234-5678 a@b.com"})
    p.post("/api/analysis", json={"source": "suggestions"})
    assert sent and all("민감한상담기록" not in t for t in sent)
    assert "010-1234-5678" not in sent[0] and "a@b.com" not in sent[0]
    db = app.state.SessionLocal()
    assert db.execute(select(Booking.professor_note)).scalar_one() == "민감한상담기록"
    db.close()


def test_external_ai_hallucinated_refs_dropped_and_failure_fallback(app, clients):
    p, s1 = clients["prof"], clients["s1"]
    s1.post("/api/suggestions", json={"category": "other", "content": "실습 시간이 부족해요"})

    class Fake:
        name = "external"

        def analyze(self, items):
            return {"summary": "요약", "themes": [{"title": "근거 없음", "item_ids": [99]},
                                                {"title": "실습", "kind": "improvement", "item_ids": [0]}]}

    app.state.settings.ai_mode = "external"
    app.state.ai_client = Fake()
    r = p.post("/api/analysis", json={"source": "suggestions"}).json()
    assert [t["title"] for t in r["themes"]] == ["실습"]
    assert r["themes"][0]["examples"] == ["실습 시간이 부족해요"]

    from app.infra.ai_client import ExternalAIError

    class Down:
        name = "external"

        def analyze(self, items):
            raise ExternalAIError("timeout")

    app.state.ai_client = Down()
    r = p.post("/api/analysis", json={"source": "suggestions"})
    assert r.status_code == 200 and r.json()["engine"] == "local-keyword"
    # AI 장애와 무관하게 기본 기능 정상
    assert s1.post("/api/suggestions", json={"category": "other", "content": "ok"}).status_code == 201


def test_ai_disabled(app, clients):
    app.state.settings.ai_mode = "disabled"
    assert clients["prof"].post("/api/analysis", json={"source": "suggestions"}).status_code == 503


def test_anonymous_writer_and_protected_board(app, clients):
    from fastapi.testclient import TestClient

    guest = TestClient(app)
    path = "/api/suggestions/anonymous"
    headers = {"X-Anonymous-Submit": "1"}
    body = {"category": "other", "content": "private guest suggestion"}
    assert guest.post(path, json=body).status_code == 403
    assert clients["s1"].post(path, json=body, headers=headers).status_code == 403
    assert guest.post(path, json=body, headers=headers).status_code == 201
    assert guest.get("/api/suggestions/public").status_code == 401
    assert clients["s1"].get("/api/suggestions/public").json() == []
    assert clients["prof"].get("/api/suggestions").json()[0]["content"] == body["content"]
    for _ in range(9):
        assert guest.post(path, json=body, headers=headers).status_code == 201
    assert guest.post(path, json=body, headers=headers).status_code == 429
    app.state.settings.feature_suggestions = False
    assert guest.post(path, json=body, headers=headers).status_code == 503
