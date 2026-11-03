# ClassBridge

교수자 1명, 최고 관리자 1명, 다수 학생을 위한 **상담 예약 · 강의 설문 · 익명 건의함** 통합 웹서비스.

- 백엔드: FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL(운영) / SQLite(개발)
- 프론트엔드: 빌드 없는 ES 모듈 (PC 주간 시간표 / 모바일 일별 카드)
- 인증: Google OpenID Connect, 서버 세션 + CSRF 토큰

> ⚠️ 실제 학생 개인정보를 받기 전에 [docs/pre-launch-checklist.md](docs/pre-launch-checklist.md)를 완료해야 합니다.

## 빠른 실행 (개발)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # 필요 시 수정
set -a && source .env && set +a
alembic upgrade head
python scripts/seed_demo.py   # 가상 데이터 (선택)
uvicorn app.main:create_app --factory --reload
```

http://localhost:8000 에서 개발용 로그인을 사용합니다.
- `admin@example.ac.kr` → 관리자, `professor@example.ac.kr` → 교수자 (`.env`의 목록 기준)
- 그 외 이메일 → 학생 (`seed_demo.py`를 실행했다면 `student1@test.ac.kr`~`student5@test.ac.kr`)

## 테스트

```bash
pytest                                   # 단위 + 통합 (SQLite)
TEST_PG_URL=postgresql+psycopg://user@host:5432/db pytest tests/postgres   # 실제 PostgreSQL 동시성·마이그레이션
python -m playwright install chromium && RUN_E2E=1 pytest tests/e2e        # 브라우저 E2E (PC·모바일)
ruff check app tests migrations scripts
```

## 문서

| 문서 | 내용 |
|---|---|
| [architecture.md](docs/architecture.md) | 계층 구조, 의존 관계, 폴더 구조, 무결성 보장 방식 |
| [permissions.md](docs/permissions.md) | 학생·교수자·관리자 권한표 |
| [database.md](docs/database.md) | 스키마, 제약, 마이그레이션, DB 계정 권한 |
| [api.md](docs/api.md) | API 명세 (코드에서 자동 생성, `scripts/gen_api_doc.py`) |
| [anonymity.md](docs/anonymity.md) | 익명성 설계와 **남은 한계** |
| [deployment.md](docs/deployment.md) | Render·Supabase·Google OAuth 배포, 백업·롤백·장애 대응 |
| [test-report.md](docs/test-report.md) | 테스트 보고서, 검증된/검증 안 된 항목 구분 |
| [pre-launch-checklist.md](docs/pre-launch-checklist.md) | 공개 배포 전 사용자 작업 목록 |
