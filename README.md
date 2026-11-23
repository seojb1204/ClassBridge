# ClassBridge

교수자 1명, 최고 관리자 1명, 다수 학생을 위한 **상담 예약 · 강의 설문 · 익명 건의함** 통합 웹서비스.

- **스테이징**: https://classbridge-staging.onrender.com (허용된 테스트 계정만 로그인 가능 · [로그인 없는 익명 건의 화면](https://classbridge-staging.onrender.com/static/suggest.html)은 누구나 열람 가능)
- **개발 브랜치**: `staging` (작업 브랜치 → PR → `staging` → Render 수동 배포)

| 학생 · 모바일 상담 예약 | 교수자 · PC 주간 시간표 |
|---|---|
| <img src="docs/screens/readme_student_mobile_booking.png" width="260" alt="학생 모바일 상담 예약 화면"> | <img src="docs/screens/readme_professor_pc_timetable.png" width="520" alt="교수자 PC 주간 시간표"> |
| **교수자 · 상담 기록·통계** | **관리자 · 작업 이력** |
| <img src="docs/screens/readme_professor_pc_insights.png" width="420" alt="상담 통계 화면"> | <img src="docs/screens/readme_admin_pc_audit.png" width="420" alt="관리 작업 이력 화면"> |

<sub>화면은 가상 데이터(`scripts/seed_demo.py`)로 캡처했습니다.</sub>

## 주요 기능

| 역할 | 할 수 있는 일 |
|---|---|
| 학생 | 주간 시간표에서 상담 예약 · 취소 없이 시간 변경 · 내 달력(.ics) 추가 · 설문 응답 · 익명 건의 (비로그인은 비공개만) |
| 교수자 | 상담 시간·강의 등록(한 문장 입력 지원) · 학생 대신 예약 · 상담 결과·비공개 기록 · 통계 · 알림(앱·Gmail·Android 푸시) · 설문 작성·결과 |
| 관리자 | 계정·역할 관리(검색·필터) · 운영 설정 · 관리 작업 이력 · 개발자 문의함 |

## 기술 스택과 설계 요점

- 백엔드: FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL(운영, Neon) / SQLite(개발)
- 프론트엔드: 빌드 없는 ES 모듈 (PC 주간 시간표 / 모바일 주간·목록 보기, PWA)
- 인증: Google OpenID Connect, 서버 세션 + CSRF 토큰, 스테이징 계정 허용 목록
- 동시 예약 무결성: 원자적 좌석 차감 + PostgreSQL 경쟁 테스트(일부러 버그를 넣으면 실패하는지 확인한 변이 검증 포함)
- 익명성: 참여 기록과 응답을 분리 저장, 소수 응답 보호, 접근 로그 차단 — **보장 범위와 한계**는 [anonymity.md](docs/anonymity.md)
- 보안 헤더: CSP(`script-src 'self'`), HSTS, `X-Frame-Options: DENY`, nosniff

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
| [anonymity.md](docs/anonymity.md) | 익명성 설계, 건의 남용 방지와 **남은 한계** |
| [deployment.md](docs/deployment.md) | Render·Neon·Google OAuth 배포, 백업·롤백·장애 대응 |
| [operations-runbook.md](docs/operations-runbook.md) | 운영 절차 |
| [test-report.md](docs/test-report.md) | 테스트 보고서, 검증된/검증 안 된 항목 구분 |
| [pre-launch-checklist.md](docs/pre-launch-checklist.md) | 공개 배포 전 사용자 작업 목록 |
| [releases/](docs/releases/) | 날짜별 변경 기록(릴리스 메모) |

운영 점검: `python scripts/retention_report.py` — 개인정보처리방침의 보관기간(365일)을 넘긴 기록 **건수만** 조회합니다(삭제하지 않음).

### 상담 우선 표시와 예약

등록된 상담은 겹치는 강의보다 우선합니다. 강의가 겹쳐도 상담의 예약·시간 변경·대리 예약 및 예약 가능 날짜 조회에는 강의 차단을 적용하지 않습니다. 정원, 예약 마감, 주말 제한과 권한 검사는 유지합니다. 기존 예약을 침범하는 새 강의 등록은 계속 거부합니다.

학생 상담 예약·변경 작성창에서 휴대폰/브라우저 뒤로가기는 창만 닫습니다. 시간표 URL과 선택 주차는 유지하며, 창을 닫은 다음 뒤로가기는 원래 페이지 이동으로 동작합니다.

학생 시간표는 로그인 사용자 전용 조회 API로 강의명·시간·강의실을 표시합니다. 강의 수정·삭제 및 관리용 조회 권한은 확대하지 않습니다. 겹치는 구간은 상담을 우선 표시합니다. 화면 알림은 터치/클릭 또는 키보드 Enter·Space·Escape로 즉시 닫을 수 있습니다.
