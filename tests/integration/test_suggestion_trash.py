from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models import AuditLog
from app.models.suggestion import Suggestion, SuggestionReply


def add_rows(app, *, trashed=2):
    ids = [str(uuid4()) for _ in range(trashed + 1)]
    with app.state.SessionLocal.begin() as db:
        for i, sid in enumerate(ids):
            db.add(Suggestion(id=sid, category='other', content='synthetic private content',
                submitted_on=date(2026, 11, 13), deleted_on=date(2026, 11, 13) if i < trashed else None))
            db.flush()
            db.add(SuggestionReply(id=str(uuid4()), suggestion_id=sid,
                content='synthetic reply', created_on=date(2026, 11, 13)))
    return ids


@pytest.mark.parametrize('role', ['prof', 'admin'])
def test_empty_trash_scope_snapshot_and_private_audit(app, clients, role):
    ids = add_rows(app, trashed=55)
    c = clients[role]
    snapshot = c.get('/api/suggestions/trash/preview').json()
    assert snapshot['count'] == 55
    assert set(snapshot['ids']) == set(ids[:-1])
    # New trash after confirmation is not part of the confirmed set.
    c.post(f'/api/suggestions/{ids[-1]}/trash')
    result = c.post('/api/suggestions/trash/empty', json={'confirmation': '영구 삭제', 'ids': snapshot['ids']})
    assert result.status_code == 200 and result.json() == {'deleted': 55}
    with app.state.SessionLocal() as db:
        assert [s.id for s in db.scalars(select(Suggestion))] == [ids[-1]]
        assert [r.suggestion_id for r in db.scalars(select(SuggestionReply))] == [ids[-1]]
        audit = db.scalar(select(AuditLog).where(AuditLog.action == 'suggestion.empty_trash'))
        assert audit.detail == {'count': 55}
        assert 'content' not in str(audit.detail)
    assert c.post('/api/suggestions/trash/empty', json={'confirmation': '영구 삭제', 'ids': []}).json() == {'deleted': 0}


def test_empty_trash_rejects_restore_race_and_duplicates_atomically(app, clients):
    ids = add_rows(app)
    c = clients['prof']
    c.post(f'/api/suggestions/{ids[0]}/restore')
    response = c.post('/api/suggestions/trash/empty', json={'confirmation': '영구 삭제', 'ids': ids[:2]})
    assert response.status_code == 409
    assert c.post('/api/suggestions/trash/empty', json={
        'confirmation': '영구 삭제', 'ids': [ids[1], ids[1]]}).status_code == 400
    assert c.post('/api/suggestions/trash/empty', json={
        'confirmation': '영구 삭제', 'ids': [str(uuid4())]}).status_code == 409
    with app.state.SessionLocal() as db:
        assert len(list(db.scalars(select(Suggestion)))) == 3
        assert len(list(db.scalars(select(SuggestionReply)))) == 3


def test_empty_trash_requires_role_confirmation_csrf_and_feature(app, clients):
    ids = add_rows(app)
    path = '/api/suggestions/trash/empty'
    body = {'confirmation': '영구 삭제', 'ids': ids[:2]}
    assert TestClient(app).get('/api/suggestions/trash/preview').status_code == 401
    assert clients['s1'].get('/api/suggestions/trash/preview').status_code == 403
    assert clients['s1'].post(path, json=body).status_code == 403
    assert clients['prof'].post(path, json={'ids': ids[:2]}).status_code == 422
    assert clients['prof'].post(path, json={'confirmation': 'no', 'ids': ids[:2]}).status_code == 422
    token = clients['prof'].headers.pop('X-CSRF-Token')
    assert clients['prof'].post(path, json=body).status_code == 403
    clients['prof'].headers['X-CSRF-Token'] = token
    app.state.settings.feature_suggestions = False
    assert clients['prof'].get('/api/suggestions/trash/preview').status_code == 503
    assert clients['prof'].post(path, json=body).status_code == 503
    with app.state.SessionLocal() as db:
        assert len(list(db.scalars(select(Suggestion)))) == 3


@pytest.mark.parametrize('role', ['prof', 'admin'])
def test_delete_selected_trash_preserves_unselected_and_new_rows(app, clients, role):
    ids = add_rows(app, trashed=4)
    c = clients[role]
    selected = [ids[0], ids[2]]
    # Later additions and individually unchecked rows must remain untouched.
    c.post(f'/api/suggestions/{ids[-1]}/trash')
    result = c.post('/api/suggestions/trash/delete-selected', json={
        'confirmation': '영구 삭제', 'ids': selected})
    assert result.status_code == 200 and result.json() == {'deleted': 2}
    with app.state.SessionLocal() as db:
        assert set(db.scalars(select(Suggestion.id))) == set(ids) - set(selected)
        assert set(db.scalars(select(SuggestionReply.suggestion_id))) == set(ids) - set(selected)
        audit = db.scalar(select(AuditLog).where(AuditLog.action == 'suggestion.delete_selected'))
        assert audit.detail == {'count': 2}


@pytest.mark.parametrize('changed', ['restored', 'missing', 'active'])
def test_delete_selected_rejects_changed_selection_atomically(app, clients, changed):
    ids = add_rows(app)
    c = clients['prof']
    selected = ids[:2]
    if changed == 'restored':
        assert c.post(f'/api/suggestions/{ids[0]}/restore').status_code == 204
    elif changed == 'missing':
        selected = [ids[1], str(uuid4())]
    else:
        selected = [ids[1], ids[-1]]
    response = c.post('/api/suggestions/trash/delete-selected', json={
        'confirmation': '영구 삭제', 'ids': selected})
    assert response.status_code == 409
    with app.state.SessionLocal() as db:
        assert set(db.scalars(select(Suggestion.id))) == set(ids)
        assert len(list(db.scalars(select(SuggestionReply)))) == 3
        assert db.scalar(select(AuditLog).where(AuditLog.action == 'suggestion.delete_selected')) is None


def test_delete_selected_validates_permission_csrf_and_request(app, clients):
    ids = add_rows(app)
    path = '/api/suggestions/trash/delete-selected'
    body = {'confirmation': '영구 삭제', 'ids': ids[:1]}
    assert TestClient(app).post(path, json=body).status_code == 401
    assert clients['s1'].post(path, json=body).status_code == 403
    c = clients['prof']
    for payload in ({'ids': ids[:1]}, {'confirmation': 'no', 'ids': ids[:1]},
                    {'confirmation': '영구 삭제', 'ids': []},
                    {'confirmation': '영구 삭제', 'ids': ['x'] * 10001}):
        assert c.post(path, json=payload).status_code == 422
    assert c.post(path, json={'confirmation': '영구 삭제', 'ids': [ids[0], ids[0]]}).status_code == 400
    token = c.headers.pop('X-CSRF-Token')
    assert c.post(path, json=body).status_code == 403
    c.headers['X-CSRF-Token'] = token
    app.state.settings.feature_suggestions = False
    assert c.post(path, json=body).status_code == 503
    with app.state.SessionLocal() as db:
        assert len(list(db.scalars(select(Suggestion)))) == 3
