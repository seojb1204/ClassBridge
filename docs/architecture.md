# 아키텍처

## 변경 전 → 변경 후

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| 저장소 상태 | `README.md` 1개 (커밋 `c43023e`, 코드 없음) | 새로 구축 |
| 지시서가 우려한 문제 (`main.py`·`app.js` 집중, 세션 권한 갱신, 마이그레이션 부재 등) | 해당 코드가 없어 재평가 불가 | 처음부터 그 문제를 피하는 구조로 설계 (아래 표) |

지시서가 우려한 항목은 다음과 같이 반영했다.

| 지시서 우려 | 대응 |
|---|---|
| `app/main.py` 기능 집중 | `main.py`는 앱 조립만 담당 (약 80줄). 도메인별 router/service/repository로 분리 |
| `static/app.js` 집중 | `js/` 아래 api·router·state·ui 공통 모듈과 화면별 `views/*.js`, 공용 `components/week-calendar.js` |
| 역할 변경 시 세션 권한 | 역할을 세션에 저장하지 않고 매 요청마다 DB에서 읽음 + 역할 변경 시 세션 삭제 |
| 마이그레이션 부재 | Alembic `0001` + 모델과 차이 없음 자동 검증 (SQLite·PostgreSQL) |
| 익명 처리 검증 부족 | 스키마·API·로그 수준 테스트와 [anonymity.md](anonymity.md) |
| PostgreSQL 동시성 테스트 부족 | 실제 PostgreSQL 16 대상 경쟁 테스트 7종 + 변이 검증 |

## 계층

```
HTTP ─▶ routers/      입력 검증(pydantic), 권한 선언 require(P.X), 상태 코드
          │
          ▼
        services/     업무 규칙: 예약 정책, 상태 전이, 설문 잠금, 익명 제출, 역할 관리
          │   └──▶ infra/  Google OIDC, 외부 AI(기본 비활성), 엑셀
          ▼
        repositories/ SQL 조회·저장, 원자적 좌석 증감
          │
          ▼
        models/       SQLAlchemy 모델 + DB 제약(CHECK, 부분 유니크 인덱스)

core/  권한표·세션·CSRF·보안 헤더·요청 제한·로그 필터·도메인 예외 (모든 계층이 사용)
```

`scripts/` 아래 의존 분석 결과(패키지 간, 실제 import 기준):

```
core          -> db, models
infra         -> config, core
repositories  -> models
services      -> config, core, db, infra, models, repositories, timeutil
routers       -> core, db, infra, repositories, schemas, services
main          -> config, core, db, infra, routers
모듈 순환 의존: 없음
```

- 서비스는 HTTP를 모른다. 도메인 예외(`core/errors.py`)만 던지고, `main.py`가 이를 상태 코드로 바꾼다. 그래서 서비스는 DB 세션만 있으면 단위·동시성 테스트를 할 수 있다(`tests/postgres`가 서비스를 직접 호출).
- 예약과 설문은 서로 import하지 않는다. 둘이 공유하는 것은 `settings_service`(운영 설정)뿐이다. 예약을 고쳐도 설문에는 영향이 없다.
- 외부 AI는 `analysis_service`를 통해서만 호출되고, 이 서비스에는 상담 기록(`professor_note`)을 읽는 코드가 없다.

## 권한: 기본 거부

- `core/permissions.py`의 표가 유일한 권한 원천이다. 알 수 없는 역할에는 빈 권한 집합을 준다.
- 모든 `/api` 라우트는 `require(P.X)`나 `require_login`을 선언해야 한다. 선언이 없는 라우트가 생기면 `test_every_api_route_declares_permission`이 실패한다(공개 예외: `/api/auth/config` 1개).
- 객체 단위 권한(남의 예약)은 서비스에서 검사하고, 남의 예약은 404로 응답해 존재 여부도 숨긴다.

## 예약 무결성 (DB가 최종 판정)

| 규칙 | 보장 수단 |
|---|---|
| 정원 초과 금지 | `UPDATE slots SET booked_count=booked_count+1 WHERE id=? AND booked_count<capacity AND status='open'` 결과가 0행이면 마감. `CHECK (booked_count <= capacity)` |
| 1인 1활성 예약 | `CREATE UNIQUE INDEX ... ON bookings(student_id) WHERE status='booked'` |
| 예약 변경 실패 시 기존 예약 보존 | 기존 취소 + 새 예약을 한 트랜잭션으로 처리, 실패 시 전체 롤백 |
| 마지막 관리자 보호 | 활성 관리자 행을 `FOR UPDATE`로 잠근 뒤(id 순서 고정, 교착 방지) 개수 확인 |

## 프론트엔드

빌드 도구 없는 ES 모듈로 FastAPI가 그대로 서빙한다. CSP가 `script-src 'self'`라서 인라인 스크립트와 스타일을 쓰지 않는다. 모든 텍스트는 `textContent`로 넣는다(`ui.js`의 `h()`). 화면의 권한 분기는 표시용일 뿐이고, 실제 판정은 서버가 한다.

```
static/js/
  main.js            시작·메뉴·라우트 등록
  api.js             fetch + CSRF
  router.js state.js ui.js time.js
  components/week-calendar.js   PC 주간표 / 모바일 일별 카드
  views/ student-booking · my-bookings · prof-slots · prof-bookings ·
         survey-editor · survey-form · surveys · suggestions · analysis · admin · login
```

## 폴더 구조

```
app/
  main.py config.py db.py timeutil.py
  core/        auth.py permissions.py identity.py errors.py middleware.py rate_limit.py
  models/      user.py booking.py survey.py suggestion.py audit.py
  schemas/     users.py bookings.py surveys.py
  repositories/ users.py bookings.py surveys.py suggestions.py audit.py settings.py
  services/    user_service.py booking_policy.py booking_service.py survey_service.py
               suggestion_service.py analysis_service.py settings_service.py
  routers/     auth.py admin.py bookings.py surveys.py suggestions.py analysis.py
  infra/       google_oauth.py ai_client.py excel.py
migrations/    Alembic (versions/0001_initial_schema.py)
static/        index.html css/app.css js/...
tests/         unit/ integration/ postgres/ e2e/
scripts/       seed_demo.py gen_api_doc.py
docs/          이 문서들
```
