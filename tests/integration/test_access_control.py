"""지시서 §2.3 접근 제어 검증 + 기본 거부(Deny by Default) 구조 검사."""
from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tests.conftest import login, make_slots

PUBLIC = {"/api/auth/config", "/api/public-surveys/{token}", "/api/public-surveys/{token}/responses"}


def _iter_api_routes(app):
    for r in app.routes:
        sub = getattr(r, "original_router", None)
        for route in (sub.routes if sub else [r]):
            if isinstance(route, APIRoute) and route.path.startswith("/api"):
                yield route


def _has_perm(dependant) -> bool:
    for d in dependant.dependencies:
        if getattr(d.call, "required_permission", None) is not None:
            return True
        if _has_perm(d):
            return True
    return False


def test_every_api_route_declares_permission(app):
    routes = list(_iter_api_routes(app))
    assert len(routes) >= 40  # 라우트 수집 자체가 실패해 검사가 공회전하지 않도록
    missing = [f"{sorted(r.methods)} {r.path}" for r in routes
               if r.path not in PUBLIC and not _has_perm(r.dependant)]
    assert missing == [], f"권한 선언 없는 API: {missing}"


def test_unauthenticated_is_rejected(app):
    c = TestClient(app)
    for path in ("/api/me", "/api/slots?start=2030-01-01", "/api/admin/users", "/api/suggestions"):
        assert c.get(path).status_code == 401, path


def test_student_cannot_call_professor_apis(clients):
    s = clients["s1"]
    assert s.post("/api/slots", json={"start_date": "2030-01-01", "start_time": "10:00",
                                      "end_time": "11:00", "duration_minutes": 30}).status_code == 403
    assert s.get("/api/bookings").status_code == 403
    assert s.get("/api/suggestions").status_code == 403
    assert s.get("/api/surveys").status_code == 403
    assert s.post("/api/analysis", json={"source": "suggestions"}).status_code == 403


def test_student_cannot_call_admin_apis(clients):
    s = clients["s1"]
    assert s.get("/api/admin/users").status_code == 403
    assert s.put(f"/api/admin/users/{s.me['id']}/role", json={"role": "admin"}).status_code == 403
    assert s.get("/api/admin/audit").status_code == 403
    assert s.put("/api/admin/settings", json={"booking_window_days": 10}).status_code == 403


def test_professor_cannot_use_admin_only(clients):
    p = clients["prof"]
    assert p.put("/api/admin/settings", json={"booking_window_days": 10}).status_code == 403
    assert p.get("/api/admin/users").status_code == 403
    assert p.put(f"/api/admin/users/{clients['s1'].me['id']}/role", json={"role": "professor"}).status_code == 403


def test_admin_can_use_all_professor_features(clients):
    a = clients["admin"]
    ids = make_slots(a)
    assert a.get("/api/bookings").status_code == 200
    r = a.post("/api/bookings", json={"slot_id": ids[0], "student_id": clients["s1"].me["id"]})
    assert r.status_code == 201, r.text
    bid = r.json()["id"]
    assert a.put(f"/api/bookings/{bid}/note", json={"note": "기록"}).status_code == 200
    assert a.get("/api/suggestions").status_code == 200
    r = a.post("/api/surveys", json={"title": "t", "questions": [{"qtype": "short", "title": "q"}]})
    assert r.status_code == 201
    assert a.get(f"/api/surveys/{r.json()['id']}/results").status_code == 200
    assert a.post("/api/analysis", json={"source": "suggestions"}).status_code == 200
    assert a.get("/api/booking-policy").status_code == 200


def test_cannot_access_other_students_booking(clients):
    p, s1, s2 = clients["prof"], clients["s1"], clients["s2"]
    ids = make_slots(p)
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    assert s2.post(f"/api/bookings/{bid}/cancel", json={}).status_code == 404
    assert s2.post(f"/api/bookings/{bid}/reschedule", json={"new_slot_id": ids[1]}).status_code == 404
    assert s2.get(f"/api/bookings/{bid}/history").status_code == 403
    assert all(b["id"] != bid for b in s2.get("/api/bookings/mine").json())
    # 학생이 다른 학생 명의로 예약 생성 불가
    assert s2.post("/api/bookings", json={"slot_id": ids[1], "student_id": s1.me["id"]}).status_code == 403


def test_student_booking_view_hides_notes(clients):
    p, s1 = clients["prof"], clients["s1"]
    ids = make_slots(p)
    bid = s1.post("/api/bookings", json={"slot_id": ids[0]}).json()["id"]
    p.put(f"/api/bookings/{bid}/note", json={"note": "비공개 상담 기록"})
    mine = s1.get("/api/bookings/mine").json()
    assert "professor_note" not in mine[0]
    assert "비공개" not in s1.get("/api/bookings/mine").text


def test_revoked_admin_session_is_rejected(app, clients):
    a = clients["admin"]
    second = login(app, "second@test.ac.kr")
    assert a.put(f"/api/admin/users/{second.me['id']}/role", json={"role": "admin"}).status_code == 200
    # 승격 시 기존 세션 무효화 → 재로그인 필요
    assert second.get("/api/me").status_code == 401
    second = login(app, "second@test.ac.kr")
    assert second.get("/api/admin/users").status_code == 200
    assert a.put(f"/api/admin/users/{second.me['id']}/role", json={"role": "student"}).status_code == 200
    assert second.get("/api/admin/users").status_code == 401  # 기존 세션 즉시 거부
    second = login(app, "second@test.ac.kr")
    assert second.get("/api/admin/users").status_code == 403


def test_client_side_role_tampering_has_no_effect(app, clients):
    s = clients["s1"]
    s.cookies.set("role", "admin")
    s.headers["X-Role"] = "admin"
    assert s.get("/api/admin/users").status_code == 403
    # dev 로그인 본문에 role을 넣어도 무시
    c = TestClient(app)
    c.post("/auth/dev/login", json={"email": "hacker@test.ac.kr", "role": "admin"})
    assert c.get("/api/me").json()["role"] == "student"


def test_csrf_required_for_mutations(clients):
    s = clients["s1"]
    token = s.headers.pop("X-CSRF-Token")
    r = s.post("/api/suggestions", json={"category": "other", "content": "x"})
    assert r.status_code == 403 and r.json()["error"] == "csrf"
    s.headers["X-CSRF-Token"] = token
    assert s.post("/api/suggestions", json={"category": "other", "content": "x"}).status_code == 201


def test_security_headers(clients):
    r = clients["s1"].get("/api/me")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Cache-Control"] == "no-store"


def test_session_cookie_flags(app):
    c = TestClient(app)
    r = c.post("/auth/dev/login", json={"email": "z@test.ac.kr"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
