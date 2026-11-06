from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from app.models import GuestParticipation, Participation, Response, User
from app.services.survey_service import AGREEMENT_SCALE


def create(p, mode="anonymous", publish=True):
    r = p.post("/api/surveys", json={"title": "수업 피드백", "access_mode": mode, "min_results": 2,
        "questions": [{"qtype": "long", "title": "개선점", "required": True},
                      {"qtype": "scale5", "title": "설명이 명확했다", "options": AGREEMENT_SCALE},
                      {"qtype": "single", "title": "장소", "options": ["서울", "강원"]}]})
    assert r.status_code == 201, r.text
    s = r.json()
    if publish:
        assert p.post(f"/api/surveys/{s['id']}/publish").status_code == 200
    return s


def test_anonymous_submit_dedup_and_no_account_link(app, clients):
    p = clients["prof"]
    s = create(p)
    guest = TestClient(app)
    path = f"/api/public-surveys/{s['public_token']}"
    page = guest.get(path)
    assert page.status_code == 200 and page.headers["Cache-Control"] == "no-store"
    assert "HttpOnly" in page.headers["set-cookie"]
    headers = {"X-Survey-CSRF": page.json()["csrf_token"]}
    answers = {str(s["questions"][0]["id"]): "설명 예시를 늘려 주세요", str(s["questions"][1]["id"]): 4,
               str(s["questions"][2]["id"]): "서울"}
    before = len(p.get("/api/students").json())
    assert guest.post(path + "/responses", json={"answers": answers}).status_code == 403
    assert guest.post(path + "/responses", headers=headers, json={"answers": {}}).status_code == 400
    assert guest.get(path).json()["participated"] is False
    assert guest.post(path + "/responses", headers=headers, json={"answers": answers}).status_code == 201
    assert guest.post(path + "/responses", headers=headers, json={"answers": answers}).status_code == 409
    assert guest.get(path).json()["participated"] is True
    assert len(p.get("/api/students").json()) == before
    assert p.get(f"/api/surveys/{s['id']}/results").json()["hidden"] is True
    assert guest.get(f"/api/surveys/{s['id']}/results").status_code == 401
    assert clients["s1"].post(f"/api/surveys/{s['id']}/responses", json={"answers": answers}).status_code == 404
    with app.state.SessionLocal() as db:
        assert len(list(db.scalars(select(GuestParticipation)))) == 1
        assert len(list(db.scalars(select(Response)))) == 1
        assert len(list(db.scalars(select(Participation)))) == 0
        assert len(list(db.scalars(select(User)))) == 5
    assert set(c["name"] for c in inspect(app.state.engine).get_columns("survey_guest_participations")) == {
        "survey_id", "browser_hash"}


def test_anonymous_availability_share_and_mode_lock(app, clients):
    p = clients["prof"]
    s = create(p, publish=False)
    path = f"/api/public-surveys/{s['public_token']}"
    guest = TestClient(app)
    assert guest.get(path).status_code == 404
    assert p.get(f"/api/surveys/{s['id']}/qr.svg").status_code == 409
    p.post(f"/api/surveys/{s['id']}/publish")
    assert p.patch(f"/api/surveys/{s['id']}", json={"access_mode": "login"}).status_code == 409
    qr = p.get(f"/api/surveys/{s['id']}/qr.svg")
    assert qr.status_code == 200 and "<svg" in qr.text
    assert clients["s1"].get(f"/api/surveys/{s['id']}/qr.svg").status_code == 403
    duplicate = p.post(f"/api/surveys/{s['id']}/duplicate").json()
    assert duplicate["access_mode"] == "anonymous" and duplicate["public_token"] != s["public_token"]
    data = guest.get(path).json()
    p.post(f"/api/surveys/{s['id']}/close")
    assert guest.get(path).json()["is_open"] is False
    assert guest.post(path + "/responses", headers={"X-Survey-CSRF": data["csrf_token"]},
                      json={"answers": {}}).status_code == 409
    p.post(f"/api/surveys/{s['id']}/trash")
    assert guest.get(path).status_code == 404
    assert guest.get("/api/public-surveys/invalid").status_code == 404


def test_scale_labels_and_login_mode_preserved(clients):
    p = clients["prof"]
    s = create(p, mode="login")
    assert s["public_token"] is None and s["questions"][1]["options"] == AGREEMENT_SCALE
    for name in ("s1", "s2"):
        assert clients[name].post(f"/api/surveys/{s['id']}/responses", json={"answers": {
            str(s["questions"][0]["id"]): "좋아요", str(s["questions"][1]["id"]): 5}}).status_code == 201
    result = p.get(f"/api/surveys/{s['id']}/results").json()
    assert result["questions"][1]["counts"][-1] == {"option": "5 · 매우 그렇다", "count": 2}


def test_logged_in_student_lists_anonymous_surveys_without_account_participation(app, clients):
    p, student = clients["prof"], clients["s1"]
    anonymous = create(p)
    login = create(p, mode="login")
    draft = create(p, publish=False)
    listing = student.get("/api/surveys/student/list").json()
    assert {row["id"] for row in listing} == {anonymous["id"], login["id"]}
    row = next(row for row in listing if row["id"] == anonymous["id"])
    assert row["access_mode"] == "anonymous" and row["public_token"] == anonymous["public_token"]
    assert draft["public_token"] not in str(listing)
    path = f"/api/public-surveys/{anonymous['public_token']}"
    opened = student.get(path).json()
    result = student.post(path + "/responses", headers={"X-Survey-CSRF": opened["csrf_token"]},
                          json={"answers": {str(anonymous["questions"][0]["id"]): "로그인해도 익명"}})
    assert result.status_code == 201
    assert student.get(path).json()["participated"] is True
    with app.state.SessionLocal() as db:
        assert list(db.scalars(select(Participation))) == []
        assert len(list(db.scalars(select(GuestParticipation)))) == 1
    p.post(f"/api/surveys/{anonymous['id']}/close")
    p.post(f"/api/surveys/{anonymous['id']}/trash")
    assert {row["id"] for row in student.get("/api/surveys/student/list").json()} == {login["id"]}
