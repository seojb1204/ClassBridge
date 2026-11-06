from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import select

from app.models import Answer, Participation, Response, Survey
from app.models.suggestion import SuggestionReply
from tests.conftest import make_slots
from tests.integration.test_surveys import _answers, _published


def test_public_board_defaults_private_and_staff_only_replies(app, clients):
    staff, student = clients["prof"], clients["s1"]
    for public, content in [(False, "private content"), (True, "public content")]:
        body = {"category": "other", "content": content}
        if public:
            body["is_public"] = True
        assert student.post("/api/suggestions", json=body).status_code == 201
    items = staff.get("/api/suggestions").json()
    private, public = sorted(items, key=lambda s: s["is_public"])
    board = student.get("/api/suggestions/public").json()
    assert [s["id"] for s in board] == [public["id"]]
    assert TestClient(app).get("/api/suggestions/public").status_code == 401
    for item in (private, public):
        path = f"/api/suggestions/{item['id']}/replies"
        assert student.post(path, json={"content": "no"}).status_code == 403
        assert staff.post(path, json={"content": "staff reply"}).status_code == 201
    board = clients["s2"].get("/api/suggestions/public").json()
    assert len(board) == 1 and board[0]["replies"][0]["content"] == "staff reply"
    assert "private content" not in str(board)
    assert set(board[0]["replies"][0]) == {"id", "content", "created_on"}


def test_suggestion_trash_restore_purge_and_permissions(app, clients):
    p, s = clients["prof"], clients["s1"]
    s.post("/api/suggestions", json={"category": "other", "content": "public", "is_public": True})
    item = p.get("/api/suggestions").json()[0]
    path = f"/api/suggestions/{item['id']}"
    p.post(path + "/replies", json={"content": "reply"})
    for action in ("trash", "restore", "purge"):
        assert s.post(path + "/" + action, json={"confirmation": "영구 삭제"}).status_code == 403
    assert p.post(path + "/purge", json={"confirmation": "영구 삭제"}).status_code == 404
    assert p.post(path + "/trash").status_code == 204
    assert s.get("/api/suggestions/public").json() == []
    assert p.get("/api/suggestions").json() == []
    assert p.get("/api/suggestions/stats").json()["total"] == 0
    assert p.post(path + "/replies", json={"content": "late"}).status_code == 404
    assert len(p.get("/api/suggestions?trash=true").json()) == 1
    assert p.post(path + "/restore").status_code == 204
    assert len(s.get("/api/suggestions/public").json()[0]["replies"]) == 1
    p.post(path + "/trash")
    assert p.post(path + "/purge", json={"confirmation": "wrong"}).status_code == 400
    assert p.post(path + "/purge", json={"confirmation": "영구 삭제"}).status_code == 204
    with app.state.SessionLocal() as db:
        assert list(db.scalars(select(SuggestionReply))) == []


def test_survey_trash_protects_responses_and_cascades_only_on_confirmed_purge(app, clients):
    p, s = clients["prof"], clients["s1"]
    sid, qids = _published(p)
    path = f"/api/surveys/{sid}"
    s.post(path + "/responses", json={"answers": _answers(qids)})
    copy_id = p.post(path + "/duplicate").json()["id"]
    # Published surveys can now be trashed directly; restore must stay closed.
    assert p.post(path + "/trash").status_code == 204
    assert s.get(f"/api/surveys/student/{sid}").status_code == 404
    assert s.post(path + "/responses", json={"answers": _answers(qids)}).status_code == 404
    assert p.get(path + "/results").status_code == 404
    assert s.get("/api/surveys/student/list").json() == []
    assert p.get("/api/surveys?trash=true").json()[0]["response_count"] == 1
    for action in ("trash", "restore", "purge"):
        assert s.post(path + "/" + action, json={"confirmation": "영구 삭제", "response_count": 1}).status_code == 403
    assert p.post(path + "/restore").status_code == 204
    assert p.get(path).json()["status"] == "closed"
    assert p.get(path + "/results").json()["response_count"] == 1
    p.post(path + "/trash")
    assert p.post(path + "/purge", json={"confirmation": "영구 삭제", "response_count": 0}).status_code == 409
    assert p.post(path + "/purge", json={"confirmation": "영구 삭제", "response_count": 1}).status_code == 204
    with app.state.SessionLocal() as db:
        for model in (Answer, Participation, Response):
            assert list(db.scalars(select(model))) == []
        assert db.get(Survey, copy_id).source_survey_id is None


def test_consultation_exports_scope_options_and_injection(app, clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    a, b = make_slots(p)
    one = s1.post("/api/bookings", json={"slot_id": a, "applicant_name": "=evil", "student_number": "PRIVATE123",
                                        "topic": "<script>alert(1)</script>"}).json()
    two = s2.post("/api/bookings", json={"slot_id": b, "applicant_name": "other-student"}).json()
    p.put(f"/api/bookings/{one['id']}/note", json={"note": "STAFF-SECRET"})
    day = one["slot"]["start_at"][:10]
    base = f"/api/exports/consultations?start={day}&end={day}"
    assert TestClient(app).get(base).status_code == 401
    assert s1.get(base + "&include_notes=true").status_code == 403
    other_id = s2.get("/api/me").json()["id"]
    assert s1.get(base + f"&student_id={other_id}").status_code == 403
    own_id = s1.get("/api/me").json()["id"]
    for suffix, count in [("", 3), (f"&student_id={own_id}", 2)]:
        response = p.get(base + suffix)
        assert response.status_code == 200
        wb = load_workbook(BytesIO(response.content))
        assert wb["상담 목록"].max_row == count
        values = str(list(wb["상담 목록"].values))
        assert "STAFF-SECRET" not in values and "PRIVATE123" not in values
        assert wb["상담 목록"]["C2"].data_type == "s"
    r = p.get(base + "&include_notes=true&include_numbers=true")
    values = str(list(load_workbook(BytesIO(r.content))["상담 목록"].values))
    assert "STAFF-SECRET" in values and "PRIVATE123" in values
    for student in (s1, s2):
        for format in ("xlsx", "csv", "print"):
            assert student.get(base + f"&format={format}").status_code == 403
    csv = p.get(base + f"&format=csv&student_id={own_id}").text
    assert "'=evil" in csv and "other-student" not in csv
    html = p.get(base + f"&format=print&student_id={own_id}").text
    assert "&lt;script&gt;" in html and "STAFF-SECRET" not in html
    assert "Cache-Control" in p.get(base).headers
    assert p.get("/api/exports/consultations?start=2020-01-01&end=2026-01-01").status_code == 400
    assert two["id"] != one["id"]
