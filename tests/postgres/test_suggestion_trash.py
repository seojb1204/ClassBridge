"""Selected deletion races are exercised against real PostgreSQL in CI."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.models import User
from app.models.suggestion import Suggestion, SuggestionReply
from app.services import feedback_management
from tests.conftest import PG_URL, login
from tests.integration.test_suggestion_trash import add_rows

pytestmark = pytest.mark.skipif(not PG_URL, reason="TEST_PG_URL 미설정")


def test_selected_delete_vs_restore_is_atomic(pg_app):
    prof = login(pg_app, 'prof@test.ac.kr')
    ids = add_rows(pg_app)
    barrier = Barrier(2)

    def action(index):
        with pg_app.state.SessionLocal() as db:
            actor = db.get(User, prof.me['id'])
            barrier.wait()
            try:
                if index == 0:
                    feedback_management.delete_selected_suggestion_trash(db, actor, ids[:2], '영구 삭제')
                else:
                    feedback_management.manage_suggestion(db, actor, ids[0], 'restore')
                return 'ok'
            except AppError:
                db.rollback()
                return 'rejected'

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(action, [0, 1]))
    assert sorted(outcomes) == ['ok', 'rejected']
    with pg_app.state.SessionLocal() as db:
        remaining = set(db.scalars(select(Suggestion.id)))
        assert remaining in ({ids[-1]}, set(ids))
        assert set(db.scalars(select(SuggestionReply.suggestion_id))) == remaining
        if outcomes[1] == 'ok':
            assert db.get(Suggestion, ids[0]).deleted_on is None
            assert db.get(Suggestion, ids[1]).deleted_on is not None
