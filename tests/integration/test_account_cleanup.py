from sqlalchemy import select

from app.models import AuthSession, User
from tests.conftest import login, make_slots


def test_empty_student_delete_revokes_session_and_allows_signup(app, clients):
    admin, student = clients["admin"], clients["s3"]
    uid = student.me["id"]
    path = f"/api/admin/users/{uid}"
    assert admin.get(path + "/deletion-preview").json()["can_delete"]
    assert student.delete(path).status_code == 403
    assert clients["prof"].delete(path).status_code == 403
    assert admin.delete(path).status_code == 200
    assert student.get("/api/me").status_code == 401
    with app.state.SessionLocal() as db:
        assert db.get(User, uid) is None
        assert not db.scalar(select(AuthSession).where(AuthSession.user_id == uid))
    again = login(app, "s3@test.ac.kr")
    assert again.me["role"] == "student"


def test_record_added_after_preview_blocks_delete_and_staff_protected(app, clients):
    admin, student = clients["admin"], clients["s1"]
    path = f"/api/admin/users/{student.me['id']}"
    assert admin.get(path + "/deletion-preview").json()["can_delete"]
    slot = make_slots(clients["prof"])[0]
    booking = student.post("/api/bookings", json={"slot_id": slot}).json()
    assert admin.delete(path).status_code == 409
    assert not admin.get(path + "/deletion-preview").json()["can_delete"]
    assert student.post(f"/api/bookings/{booking['id']}/cancel", json={}).status_code == 200
    assert admin.delete(path).status_code == 409  # cancelled history is also protected
    for role in ("admin", "prof"):
        assert admin.delete(f"/api/admin/users/{clients[role].me['id']}").status_code == 403
    assert student.get("/api/me").status_code == 200
