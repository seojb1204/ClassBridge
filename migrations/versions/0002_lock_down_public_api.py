"""Supabase 공개 API(Data API) 경로 차단

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03

ClassBridge는 FastAPI가 PostgreSQL에 직접 접속하고, Supabase Data API(PostgREST)는 쓰지 않는다.
Supabase는 public 스키마의 테이블에 anon·authenticated 역할 권한을 기본으로 주기 때문에,
anon 키만 있으면 REST로 테이블을 읽을 수 있는 경로가 열려 있다. 이 마이그레이션은 그 경로를 닫는다.

1. 모든 public 테이블에 RLS(행 수준 보안)를 켠다. 정책이 없으므로 anon·authenticated는 0행만 보인다.
   앱은 테이블 소유자(postgres)로 접속하므로 RLS의 영향을 받지 않는다(FORCE 미사용).
2. anon·authenticated의 테이블·시퀀스·함수 권한을 회수하고, 앞으로 만들 객체의 기본 권한도 회수한다.

일반 PostgreSQL(로컬·CI)에는 anon·authenticated 역할이 없으므로 RLS만 켜고 권한 회수는 건너뛴다.
SQLite에서는 아무것도 하지 않는다.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SUPABASE_API_ROLES = ("anon", "authenticated")


def _public_tables(bind) -> list[str]:
    rows = bind.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"))
    return [r[0] for r in rows]


def _existing_api_roles(bind) -> list[str]:
    rows = bind.execute(sa.text("SELECT rolname FROM pg_roles WHERE rolname = ANY(:names) ORDER BY rolname"),
                        {"names": list(SUPABASE_API_ROLES)})
    return [r[0] for r in rows]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in _public_tables(bind):
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')
    roles = _existing_api_roles(bind)
    if not roles:
        return
    targets = ", ".join(f'"{r}"' for r in roles)
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {targets}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {targets}")
    op.execute(f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {targets}")
    # 이후 마이그레이션이 만드는 객체에도 자동으로 권한이 붙지 않도록 (현재 접속 역할이 만든 객체 기준)
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {targets}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {targets}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM {targets}")


def downgrade() -> None:
    # RLS만 끈다. 회수한 권한은 보안상 되돌리지 않는다(필요하면 사람이 명시적으로 GRANT).
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in _public_tables(bind):
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
