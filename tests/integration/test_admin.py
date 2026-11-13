from __future__ import annotations

from tests.conftest import ADMIN, build_app, login


def test_bootstrap_roles_from_env_allowlist(clients):
    assert clients["admin"].me["role"] == "admin"
    assert clients["prof"].me["role"] == "professor"
    assert clients["s1"].me["role"] == "student"


def test_admin_cannot_change_own_role(clients):
    a = clients["admin"]
    r = a.put(f"/api/admin/users/{a.me['id']}/role", json={"role": "student"})
    assert r.status_code == 403


def test_last_admin_cannot_be_demoted_or_deactivated(app, clients):
    a = clients["admin"]
    other = login(app, "b@test.ac.kr")
    a.put(f"/api/admin/users/{other.me['id']}/role", json={"role": "admin"})
    other = login(app, "b@test.ac.kr")
    # other가 원래 관리자를 강등 → 관리자 1명 남음
    assert other.put(f"/api/admin/users/{a.me['id']}/role", json={"role": "professor"}).status_code == 200
    # 이제 other가 유일한 관리자. 다른 관리자가 없으니 자기 자신 강등은 금지(자기 변경 금지)
    assert other.put(f"/api/admin/users/{other.me['id']}/role", json={"role": "student"}).status_code == 403
    assert other.put(f"/api/admin/users/{other.me['id']}/active", json={"is_active": False}).status_code == 403


def test_last_admin_guard_in_service(app, clients):
    """자기 변경 금지와 별개로, 서비스 계층이 마지막 관리자 보호를 수행하는지 직접 검증."""
    import pytest

    from app.core.errors import Conflict
    from app.models import User
    from app.services import user_service
    db = app.state.SessionLocal()
    try:
        admin = db.query(User).filter_by(email=ADMIN).one()
        fake_actor = User(id=-1, role="admin", email="x", google_sub="x")
        with pytest.raises(Conflict):
            user_service.change_role(db, fake_actor, admin.id, "student")
    finally:
        db.close()


def test_deactivation_kills_sessions_and_blocks_login(app, clients):
    a, s1 = clients["admin"], clients["s1"]
    assert a.put(f"/api/admin/users/{s1.me['id']}/active", json={"is_active": False}).status_code == 200
    assert s1.get("/api/me").status_code == 401
    from fastapi.testclient import TestClient
    c = TestClient(app)
    assert c.post("/auth/dev/login", json={"email": "s1@test.ac.kr"}).status_code == 403
    a.put(f"/api/admin/users/{s1.me['id']}/active", json={"is_active": True})
    assert login(app, "s1@test.ac.kr").get("/api/me").status_code == 200


def test_role_change_is_audited(clients):
    a, s1 = clients["admin"], clients["s1"]
    a.put(f"/api/admin/users/{s1.me['id']}/role", json={"role": "professor"})
    logs = a.get("/api/admin/audit?action=user.role_change").json()
    assert logs and logs[0]["detail"] == {"email": "s1@test.ac.kr", "from": "student", "to": "professor"}
    assert logs[0]["actor_id"] == a.me["id"]


def test_env_allowlist_does_not_promote_existing_user_when_admin_exists(tmp_path):
    """허용 목록에 나중에 추가돼도, 활성 관리자가 있으면 자동 승격되지 않는다."""
    app = build_app(f"sqlite:///{tmp_path}/a.db")
    login(app, ADMIN)
    s = login(app, "late@test.ac.kr")
    assert s.me["role"] == "student"
    app.state.settings.admin_emails.append("late@test.ac.kr")
    assert login(app, "late@test.ac.kr").me["role"] == "student"


def test_env_allowlist_recovers_when_no_admin(tmp_path):
    app = build_app(f"sqlite:///{tmp_path}/b.db", admin_emails=[])
    s = login(app, "owner@test.ac.kr")
    assert s.me["role"] == "student"
    app.state.settings.admin_emails.append("owner@test.ac.kr")
    assert login(app, "owner@test.ac.kr").me["role"] == "admin"


def test_settings_update_and_validation(clients):
    a = clients["admin"]
    assert a.put("/api/admin/settings", json={"booking_window_days": 14}).json()["values"]["booking_window_days"] == 14
    assert a.put("/api/admin/settings", json={"booking_window_days": 0}).status_code == 400
    assert a.put("/api/admin/settings", json={"unknown": 1}).status_code == 400
    assert a.put("/api/admin/settings", json={"cancel_deadline_hours": True}).status_code == 400


def test_domain_restriction(tmp_path):
    from fastapi.testclient import TestClient
    app = build_app(f"sqlite:///{tmp_path}/c.db", allowed_email_domains=["test.ac.kr"])
    c = TestClient(app)
    assert c.post("/auth/dev/login", json={"email": "x@gmail.com"}).status_code == 403
    assert c.post("/auth/dev/login", json={"email": "x@test.ac.kr"}).status_code == 200


def test_unified_deadline_ignores_stored_cancellation_setting(app, clients):
    from app.models import AppSetting
    with app.state.SessionLocal.begin() as db:
        db.add(AppSetting(key="cancel_deadline_hours", value=3))
    policy = clients["s1"].get("/api/booking-policy").json()
    assert policy["booking_deadline_minutes"] == policy["cancel_deadline_minutes"] == 30
    assert policy["cancel_deadline_hours"] == 0.5
    settings = clients["admin"].get("/api/admin/settings").json()
    assert "cancel_deadline_hours" not in {s["key"] for s in settings["specs"]}
    assert "취소·변경" in next(s["label"] for s in settings["specs"] if s["key"] == "booking_deadline_minutes")


def test_unified_deadline_legacy_write_conflict_is_atomic(clients):
    a = clients["admin"]
    assert a.put("/api/admin/settings", json={"booking_deadline_minutes": 30,
                                            "cancel_deadline_hours": 3}).status_code == 400
    assert a.put("/api/admin/settings", json={"cancel_deadline_hours": 0.5}).status_code == 200
    assert a.put("/api/admin/settings", json={"booking_deadline_hours": 1}).status_code == 200
    policy = clients["s1"].get("/api/booking-policy").json()
    assert policy["booking_deadline_minutes"] == policy["cancel_deadline_minutes"] == 60
    assert a.put("/api/admin/settings", json={"booking_deadline_minutes": 30,
                                            "cancel_deadline_hours": 0.5}).status_code == 200


def test_unified_deadline_legacy_precedence_and_storage_preserved(app, clients):
    from app.models import AppSetting
    with app.state.SessionLocal.begin() as db:
        db.add(AppSetting(key="cancel_deadline_hours", value=7))
        db.add(AppSetting(key="booking_deadline_hours", value=2))
    assert clients["s1"].get("/api/booking-policy").json()["cancel_deadline_minutes"] == 120
    with app.state.SessionLocal.begin() as db:
        db.add(AppSetting(key="booking_deadline_minutes", value=30))
    policy = clients["s1"].get("/api/booking-policy").json()
    assert policy["booking_deadline_minutes"] == policy["cancel_deadline_minutes"] == 30
    with app.state.SessionLocal() as db:
        assert db.get(AppSetting, "cancel_deadline_hours").value == 7
        assert db.get(AppSetting, "booking_deadline_hours").value == 2
