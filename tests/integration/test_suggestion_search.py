from datetime import date

from app.models import Suggestion


def seed(app):
    with app.state.SessionLocal.begin() as db:
        db.add_all([
            Suggestion(id='a', category='lecture', content='100% 개선 _ 제안', status='new',
                       submitted_on=date(2026, 1, 2), is_public=False),
            Suggestion(id='b', category='other', content='일반 개선', status='reviewed',
                       submitted_on=date(2026, 1, 2), is_public=True),
            Suggestion(id='c', category='lecture', content='오래된 제안', status='archived',
                       submitted_on=date(2026, 1, 1), is_public=False),
            Suggestion(id='d', category='lecture', content='휴지통 제안', status='new',
                       submitted_on=date(2026, 1, 3), deleted_on=date(2026, 1, 4), is_public=False),
        ])


def test_staff_search_is_literal_scoped_and_does_not_expose_private_to_student(app, clients):
    seed(app)
    url = '/api/suggestions/search'
    for role in ['prof', 'admin']:
        assert [x['id'] for x in clients[role].post(url, json={'query': '%'}).json()] == ['a']
        assert [x['id'] for x in clients[role].post(url, json={'query': '_'}).json()] == ['a']
        assert [x['id'] for x in clients[role].post(url, json={'query': '제안', 'status': 'archived'}).json()] == ['c']
        assert [x['id'] for x in clients[role].post(url, json={'query': '제안', 'trash': True}).json()] == ['d']
    assert clients['s1'].post(url, json={'query': '제안'}).status_code == 403
    assert [x['id'] for x in clients['s1'].get('/api/suggestions/public').json()] == ['b']


def test_date_sort_preserves_same_day_uuid_order_and_pagination(app, clients):
    seed(app)
    staff = clients['prof']
    assert [x['id'] for x in staff.get('/api/suggestions').json()] == ['a', 'b', 'c']
    assert [x['id'] for x in staff.get('/api/suggestions?order=oldest').json()] == ['c', 'a', 'b']
    assert [x['id'] for x in staff.post('/api/suggestions/search', json={
        'query': '개선', 'limit': 1, 'offset': 1}).json()] == ['b']
    response = staff.post('/api/suggestions/search', json={'query': 'private' * 50})
    assert response.status_code == 422
    assert 'private' not in response.text
    assert staff.post('/api/suggestions/search', json={'order': 'unsafe'}).status_code == 422
