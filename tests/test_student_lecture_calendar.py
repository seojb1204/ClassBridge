from fastapi.testclient import TestClient

from tests.conftest import future_day
from tests.test_lectures import body


def test_student_lecture_calendar_read_only_minimal_fields(clients, app):
    p, student = clients['prof'], clients['s1']
    row = p.post('/api/lectures', json=body()).json()[0]
    params = {'start': future_day().isoformat()}
    row = p.get('/api/lectures', params=params).json()[0]
    assert TestClient(app).get('/api/lectures/calendar', params=params).status_code == 401
    response = student.get('/api/lectures/calendar', params=params)
    assert response.status_code == 200
    assert response.json() == [{k: row[k] for k in
        ('id', 'title', 'location', 'start_at', 'end_at', 'event_type', 'bookable')}]
    assert student.get('/api/lectures', params=params).status_code == 403
    assert student.post('/api/lectures', json=body()).status_code == 403
    assert student.patch(f"/api/lectures/{row['id']}", json=body()).status_code == 403
    assert student.post(f"/api/lectures/{row['id']}/cancel").status_code == 403
    assert student.get('/api/lectures/calendar', params={**params, 'days': 91}).status_code == 422
    assert p.post(f"/api/lectures/{row['id']}/cancel").status_code == 200
    assert student.get('/api/lectures/calendar', params=params).json() == []
