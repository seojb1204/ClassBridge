from app.models import Slot
from tests.conftest import future_day, make_slots


def test_delete_only_cancelled_slots_without_any_booking_history(app, clients):
    professor, student = clients["prof"], clients["s1"]
    ids = make_slots(professor)
    path = f"/api/slots/{ids[0]}"
    assert student.delete(path).status_code == 403
    assert professor.delete(path).status_code == 409
    professor.post(path + "/cancel", json={})
    listing = professor.get(f"/api/slots?start={future_day()}&days=1").json()
    assert next(s for s in listing if s["id"] == ids[0])["can_delete"] is True
    assert professor.delete(path).status_code == 204
    assert professor.delete(path).status_code == 404
    with app.state.SessionLocal() as db:
        assert db.get(Slot, ids[0]) is None
    booking = student.post("/api/bookings", json={"slot_id": ids[1]}).json()
    student.post(f"/api/bookings/{booking['id']}/cancel", json={})
    professor.post(f"/api/slots/{ids[1]}/cancel", json={})
    assert professor.delete(f"/api/slots/{ids[1]}").status_code == 409
    listing = professor.get(f"/api/slots?start={future_day()}&days=1").json()
    assert next(s for s in listing if s["id"] == ids[1])["can_delete"] is False
    assert len(student.get("/api/bookings/mine").json()) == 1


def test_other_creator_protected_and_admin_can_remove_empty(clients):
    admin, professor = clients["admin"], clients["prof"]
    sid = make_slots(admin)[0]
    admin.post(f"/api/slots/{sid}/cancel", json={})
    assert professor.delete(f"/api/slots/{sid}").status_code == 403
    assert admin.delete(f"/api/slots/{sid}").status_code == 204


def test_rescheduled_booking_history_also_prevents_delete(clients):
    professor, student = clients["prof"], clients["s1"]
    ids = make_slots(professor)
    booking = student.post("/api/bookings", json={"slot_id": ids[0]}).json()
    moved = student.post(f"/api/bookings/{booking['id']}/reschedule", json={"new_slot_id": ids[1]})
    assert moved.status_code == 200
    professor.post(f"/api/slots/{ids[0]}/cancel", json={})
    assert professor.delete(f"/api/slots/{ids[0]}").status_code == 409
