"""설문: 편집 정책, 익명 제출, 중복 방지, 결과 임계값, 내보내기."""
from __future__ import annotations

from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import inspect

from tests.conftest import login

QUESTIONS = [
    {"qtype": "short", "title": "한 줄 소감", "required": False},
    {"qtype": "long", "title": "개선점", "required": False},
    {"qtype": "single", "title": "난이도", "required": True, "options": ["쉬움", "보통", "어려움"]},
    {"qtype": "multi", "title": "좋았던 점", "options": ["실습", "강의", "과제"]},
    {"qtype": "dropdown", "title": "학년", "options": ["1", "2", "3"]},
    {"qtype": "scale5", "title": "만족도", "required": True},
]


def _published(p, min_results=2):
    r = p.post("/api/surveys", json={"title": "중간 설문", "questions": QUESTIONS, "min_results": min_results})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert p.post(f"/api/surveys/{sid}/publish").status_code == 200
    qids = [q["id"] for q in r.json()["questions"]]
    return sid, qids


def _answers(qids, short="좋아요", level="보통", scale=4):
    return {str(qids[0]): short, str(qids[1]): "과제가 많아요", str(qids[2]): level,
            str(qids[3]): ["실습", "과제"], str(qids[4]): "2", str(qids[5]): scale}


def test_full_survey_flow(clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    sid, qids = _published(p)
    lst = s1.get("/api/surveys/student/list").json()
    assert lst[0]["is_open"] and not lst[0]["participated"]
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids)}).status_code == 201
    # 결과: 1건이면 임계값(2) 미만 → 숨김
    res = p.get(f"/api/surveys/{sid}/results").json()
    assert res["hidden"] and res["response_count"] == 1 and res["questions"] == []
    assert s2.post(f"/api/surveys/{sid}/responses",
                   json={"answers": _answers(qids, short="=HYPERLINK(\"x\")", level="어려움", scale=2)}).status_code == 201
    res = p.get(f"/api/surveys/{sid}/results").json()
    assert not res["hidden"] and res["response_count"] == 2
    level = next(q for q in res["questions"] if q["title"] == "난이도")
    assert {c["option"]: c["count"] for c in level["counts"]} == {"쉬움": 0, "보통": 1, "어려움": 1}
    scale = next(q for q in res["questions"] if q["qtype"] == "scale5")
    assert scale["average"] == 3.0
    multi = next(q for q in res["questions"] if q["qtype"] == "multi")
    assert {c["option"]: c["count"] for c in multi["counts"]} == {"실습": 2, "강의": 0, "과제": 2}
    assert s1.get("/api/surveys/student/list").json()[0]["participated"] is True


def test_duplicate_submission_blocked(clients):
    p, s1 = clients["prof"], clients["s1"]
    sid, qids = _published(p)
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids)}).status_code == 201
    r = s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids)})
    assert r.status_code == 409 and r.json()["error"] == "already_participated"


def test_answer_validation(clients):
    p, s1 = clients["prof"], clients["s1"]
    sid, qids = _published(p)
    bad = _answers(qids)
    bad[str(qids[2])] = "없는선택지"
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": bad}).status_code == 400
    missing = _answers(qids)
    del missing[str(qids[5])]
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": missing}).status_code == 400
    bad = _answers(qids)
    bad[str(qids[5])] = 7
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": bad}).status_code == 400
    bad = _answers(qids)
    bad["99999"] = "x"
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": bad}).status_code == 400
    # 실패한 제출은 참여로 기록되지 않음 → 정상 제출 가능
    assert s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids)}).status_code == 201


def test_questions_locked_after_publish_and_duplicate(clients):
    p = clients["prof"]
    sid, _ = _published(p)
    r = p.patch(f"/api/surveys/{sid}", json={"questions": [{"qtype": "short", "title": "바뀜"}]})
    assert r.status_code == 409 and r.json()["error"] == "survey_locked"
    assert p.patch(f"/api/surveys/{sid}", json={"title": "제목만 수정"}).status_code == 200
    dup = p.post(f"/api/surveys/{sid}/duplicate").json()
    assert dup["status"] == "draft" and dup["source_survey_id"] == sid and len(dup["questions"]) == len(QUESTIONS)
    r = p.patch(f"/api/surveys/{dup['id']}", json={"questions": [{"qtype": "short", "title": "새 문항"}]})
    assert r.status_code == 200 and len(r.json()["questions"]) == 1


def test_draft_not_visible_and_closed_not_submittable(clients):
    p, s1 = clients["prof"], clients["s1"]
    draft = p.post("/api/surveys", json={"title": "초안", "questions": QUESTIONS}).json()
    assert s1.get(f"/api/surveys/student/{draft['id']}").status_code == 404
    assert all(x["id"] != draft["id"] for x in s1.get("/api/surveys/student/list").json())
    sid, qids = _published(p)
    p.post(f"/api/surveys/{sid}/close")
    r = s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids)})
    assert r.status_code == 409 and r.json()["error"] == "survey_closed"


def test_question_validation(clients):
    p = clients["prof"]
    r = p.post("/api/surveys", json={"title": "x", "questions": [{"qtype": "single", "title": "a", "options": ["1"]}]})
    assert r.status_code == 400
    r = p.post("/api/surveys", json={"title": "x", "questions": [{"qtype": "single", "title": "a", "options": ["1", "1"]}]})
    assert r.status_code == 400
    empty = p.post("/api/surveys", json={"title": "x"}).json()
    assert p.post(f"/api/surveys/{empty['id']}/publish").status_code == 400


def test_export_xlsx_sanitizes_formulas(clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    sid, qids = _published(p)
    s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids, short="=1+1")})
    assert p.get(f"/api/surveys/{sid}/export.xlsx").status_code == 409  # 임계값 미만
    s2.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids, short="@SUM(A1)")})
    r = p.get(f"/api/surveys/{sid}/export.xlsx")
    assert r.status_code == 200
    wb = load_workbook(BytesIO(r.content))
    vals = [c.value for row in wb["응답"].iter_rows(min_row=2) for c in row]
    assert "'=1+1" in vals and "'@SUM(A1)" in vals
    assert not any(isinstance(v, str) and v.startswith(("=", "@")) for v in vals)
    assert s1.get(f"/api/surveys/{sid}/export.xlsx").status_code == 403


def test_anonymity_schema_has_no_link(app):
    """응답 테이블에 사용자 ID·시각 컬럼이 없고, 참여 테이블에는 시각 컬럼이 없다."""
    insp = inspect(app.state.engine)
    resp_cols = {c["name"] for c in insp.get_columns("survey_responses")}
    ans_cols = {c["name"] for c in insp.get_columns("survey_answers")}
    part_cols = {c["name"] for c in insp.get_columns("survey_participations")}
    sugg_cols = {c["name"] for c in insp.get_columns("suggestions")}
    assert resp_cols == {"id", "survey_id"}
    assert ans_cols == {"id", "response_id", "question_id", "value"}
    assert part_cols == {"survey_id", "user_id"}
    assert not ({"user_id", "author_id", "created_at", "ip"} & sugg_cols)


def test_staff_cannot_see_who_participated(clients):
    p, s1 = clients["prof"], clients["s1"]
    sid, qids = _published(p)
    s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids)})
    texts = [p.get(f"/api/surveys/{sid}/results").text, p.get("/api/surveys").text,
             p.get(f"/api/surveys/{sid}").text]
    assert all("s1@test.ac.kr" not in t and "학생1" not in t for t in texts)
    assert all("participants" not in t for t in texts)


def test_no_submission_audit_or_log(app, clients, caplog):
    p, s1, a = clients["prof"], clients["s1"], clients["admin"]
    sid, qids = _published(p)
    with caplog.at_level("DEBUG"):
        s1.post(f"/api/surveys/{sid}/responses", json={"answers": _answers(qids, short="비밀소감")})
    assert "비밀소감" not in caplog.text
    actions = {x["action"] for x in a.get("/api/admin/audit?limit=500").json()}
    assert not any("response" in act or "submit" in act for act in actions)


def test_feature_flag_disables_surveys(tmp_path):
    from tests.conftest import build_app
    app = build_app(f"sqlite:///{tmp_path}/f.db", feature_surveys=False)
    s = login(app, "s@test.ac.kr")
    assert s.get("/api/surveys/student/list").status_code == 503
