# 배포 · 운영 가이드 (Render + Neon PostgreSQL + Google OAuth)

> 이 문서의 절차는 **실제 계정에서 실행해 검증하지 않았다**. 유료 결제, 공개 배포, 실제 학생 데이터 입력은 사용자 승인과 개인정보 검토가 끝난 뒤에 진행한다.

## 0. 구성 검토

| 구성 | 선택 | 근거 / 주의 |
|---|---|---|
| 웹 서버 | Render Web Service | FastAPI를 그대로 실행, `render.yaml` 제공. **무료 플랜은 15분간 요청이 없으면 휴면**해서 첫 접속이 수십 초 걸릴 수 있다. 수업 중 사용이 잦다면 유료 플랜(월 7달러 수준, 가격은 직접 확인)을 검토한다. |
| DB | Neon PostgreSQL | 무료 플랜에서는 유휴 시 컴퓨팅이 자동 중지되므로 재연결 지연이 있을 수 있다. 백업/복구 한도와 정기 백업 책임을 확인한다. |
| 인증 | Google Cloud OAuth (OIDC) | 무료. 외부 사용자 대상이면 OAuth 동의 화면 게시가 필요하다. |
| CI | GitHub Actions | `.github/workflows/ci.yml` (PostgreSQL 서비스와 E2E 포함) |

단일 인스턴스를 전제로 한다. 요청 제한이 메모리 기반이라 인스턴스를 여러 대로 늘리면 Redis 같은 공유 저장소로 바꿔야 한다.

## 1. 환경 분리

| 환경 | APP_ENV | DB | 로그인 |
|---|---|---|---|
| 개발 | development | SQLite 파일 | 개발용 이메일 로그인 |
| 테스트/CI | test | SQLite + PostgreSQL(CI 서비스) | 개발용 로그인 / 가짜 검증기 |
| 비공개 스테이징 | production + STAGING_MODE=true | 별도 Neon 프로젝트 | Google (명시적 허용 목록 계정만) |
| 운영 | production | 운영 전용 PostgreSQL | Google |

`APP_ENV=production`에서는 다음 중 하나라도 해당하면 **서버가 시작을 거부한다**: 개발 로그인이 켜져 있음, SECRET_KEY가 짧음, `COOKIE_SECURE=false`, SQLite, Google 키 없음, `ADMIN_EMAILS` 없음(`app/config.py`). 추가로 `STAGING_MODE=true`이면 `STAGING_ALLOWED_EMAILS`가 비어 있거나 관리자·교수 이메일이 빠진 경우에도 시작을 거부한다. 해당 목록 밖의 Google 계정은 로그인할 수 없다.

## 2. Google OAuth 설정

1. Google Cloud Console → 새 프로젝트 → "API 및 서비스" → "OAuth 동의 화면"
   - 사용자 유형: 외부(학교 Workspace라면 내부)
   - 범위: `openid`, `email`, `profile`만
   - 테스트 단계에서는 "테스트 사용자"에 허용된 관리자·교수자·학생 시험용 계정만 추가
2. "사용자 인증 정보" → "OAuth 클라이언트 ID" → 웹 애플리케이션
   - 승인된 리디렉션 URI: `https://<도메인>/auth/google/callback`
3. 발급된 ID와 시크릿을 Render 환경변수 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`에 넣는다(코드나 Git에는 넣지 않는다).
4. **학생의 개인 Gmail 로그인을 허용하는 확정 정책에 따라** `ALLOWED_EMAIL_DOMAINS`는 비워 둔다. Google 계정 소유 확인만 가능하며 링크 소지자가 실제 수강생인지 검증하지 못하므로, 공개 전 위협·운영 정책을 확인한다.

## 3. Neon PostgreSQL 설정

1. **ClassBridge 전용 무료 Neon 프로젝트**를 생성한다. 기존 Supabase 프로젝트는 변경하지 않는다. Neon 계정 연결·생성은 사용자의 로그인과 앱 승인 후 진행한다.
2. Neon Console의 **Connect**에서 서로 다른 두 연결 문자열을 준비한다.
   - `DATABASE_URL`: 애플리케이션 서버에서 사용할 **Pooled** 연결 문자열 (호스트에 `-pooler` 포함)
   - `DATABASE_URL_DIRECT`: Alembic 마이그레이션·백업에 사용할 **Direct** 연결 문자열 (호스트에 `-pooler` 없음)
   - 둘 다 `sslmode=require` 등을 유지한다. 비밀번호가 포함된 URL은 GitHub·문서·채팅에 기입하지 않는다.
3. Render의 비밀 환경변수로 두 URL을 지정한다. `migrations/env.py`는 `DATABASE_URL_DIRECT`를 우선 사용하고, 평상시 FastAPI는 `DATABASE_URL`을 사용한다.
4. 마이그레이션 `0001 → 0002 → 0003 → 0004`를 **새 DB에만** 검토·적용한다. `0002`의 RLS 설정은 원래 Supabase 공개 API 차단 목적이며 일반 PostgreSQL에는 `anon/authenticated` 역할 권한 회수 없이 RLS만 켠다. 실제 연결 계정이 테이블 소유자이며 서비스가 정상 동작하는지 반드시 검증한다.
5. 개인·단체 예약 및 시간표 동시 등록 테스트를 실제 Neon 환경에서 실행한다. 테스트 데이터 외에 실제 학생 개인정보를 넣지 않는다.
6. 무료 요금제는 용량·컴퓨팅·복원 기간 제한이 있으므로 운영 데이터로 전환하기 전 백업을 복구한 실제 결과와 함께 평가한다.

Neon 공식 연결 문서: https://neon.com/docs/get-started/connect-neon

## 4. Render 배포

1. Render → New → Blueprint → 이 저장소 선택(`render.yaml`), 또는 Web Service를 수동 생성
2. 환경변수 입력 (`.env.example` 참고): `BASE_URL=https://<서비스>.onrender.com`, `DATABASE_URL`(pooled), `DATABASE_URL_DIRECT`(direct), `ADMIN_EMAILS`, `PROFESSOR_EMAILS`, `STAGING_MODE=true`, `STAGING_ALLOWED_EMAILS`(가상 데이터로 테스트할 Google 계정 목록)
3. 배포하면 시작 명령에서 `alembic upgrade head`를 실행한 뒤 서버를 띄우고 `/healthz`를 확인한다. 마이그레이션이 실패하면 서버가 뜨지 않아 새 버전이 실패 처리되고, 이전 버전이 계속 서비스된다.
4. 사용자 지정 도메인은 Render → Custom Domains에서 연결하고 HTTPS 인증서를 자동 발급받는다. `BASE_URL`과 Google 리디렉션 URI도 함께 바꾼다.

## 5. 관리자 초기 등록

1. `ADMIN_EMAILS`에 최고 관리자 이메일, `PROFESSOR_EMAILS`에 교수 이메일을 넣는다.
2. 두 사람이 Google로 처음 로그인하면 역할이 자동 부여되고 감사 로그(`user.bootstrap_role`)에 남는다.
3. 이후 역할은 앱의 "계정·권한" 화면에서만 바꾼다(환경변수는 신규 계정에만 적용).
4. 관리자 계정에는 Google 2단계 인증을 반드시 켠다(앱 자체 MFA는 없음, Google 계정 보안에 의존).

## 6. 로그 · 모니터링

- Render Logs: 애플리케이션 오류. 익명 제출 경로의 접근 로그는 앱에서 걸러지지만, Render 엣지 로그는 별도로 남는다(익명성 문서 L3).
- `/healthz`: 웹 서버 생존만 확인하며 DB 쿼리를 실행하지 않는다. Render 상태 확인은 이 경로를 사용한다.
- `/readyz`: DB 연결까지 확인하는 수동 배포 점검용 경로다. 이 경로에 잦은 외부 모니터링을 붙이면 Neon 휴면을 막는다.
- 상담 자동 완료와 알림은 다음 예약 종료·발송 시각에 실행하고, 앱의 변경 요청 후 즉시 다시 확인한다. 일이 없으면 최대 6시간 대기한다. 기존 단일 인스턴스 전제이며, 다중 프로세스·외부 DB 변경 시에는 공유 스케줄러가 필요하다. 서버가 휴면 중이면 알림 실행은 보장되지 않으므로 예약 알림을 운영하는 서버는 실행 상태를 유지해야 한다.
- DB 장애 시 API는 503 `db_unavailable`을 반환한다.

## 7. 백업 · 복구

```bash
# 백업 (매주 + 학기 중요 시점, 암호화 저장소에 보관)
pg_dump "$DATABASE_URL_DIRECT" --format=custom --no-owner --file=classbridge-$(date +%Y%m%d).dump

# 복구 (새 DB에 먼저 복원해 검증한 뒤 전환)
pg_restore --clean --if-exists --no-owner --dbname="$RESTORE_DATABASE_URL" classbridge-YYYYMMDD.dump
```

백업 파일에는 개인정보와 익명 응답이 들어 있다. 열람자를 관리자로 한정하고, 보유기간이 정해지면 그에 맞춰 파기한다.

## 8. 롤백

| 상황 | 절차 |
|---|---|
| 새 코드에 버그 (스키마 변경 없음) | Render → Deploys → 이전 배포에서 "Rollback" |
| 새 마이그레이션이 포함된 배포 | ① 이전 배포로 롤백 ② 필요하면 `alembic downgrade -1`(되돌리는 방향에 데이터 손실이 있으면 **실행 전 백업 필수**, 사용자 승인) |
| 데이터 손상 | 서비스 일시 중단 → 최근 백업을 새 DB에 복원 → 검증 → `DATABASE_URL` 전환 |

원칙: 마이그레이션은 "추가 후 전환" 방식으로 만들어서, 이전 코드도 새 스키마에서 동작하도록 한다.

## 9. 장애 대응

| 증상 | 확인 | 조치 |
|---|---|---|
| 첫 접속이 매우 느림 | 무료 플랜 휴면 | 정상. 상시 사용이면 유료 플랜 검토 |
| 503 db_unavailable | Neon 컴퓨팅 상태, 사용량 한도·접속 문자열 | Neon 프로젝트 상태·보안 연결 확인 |
| 로그인 실패 (state 불일치) | 쿠키 차단, BASE_URL 불일치 | `BASE_URL`과 리디렉션 URI 일치 확인 |
| 서버 시작 실패 ConfigError | Render 로그 메시지 | 메시지에 나온 환경변수 수정 |
| 관리자 계정 분실 | 활성 관리자 0명? | `ADMIN_EMAILS`에 새 관리자 이메일 추가 → 해당 계정으로 로그인하면 자동 복구 |
| AI 분석 실패 | 외부 API 상태 | 자동으로 로컬 분석으로 대체됨. 기본 기능은 영향 없음 |

## 10. 배포 후 점검 (스모크 테스트)

- [ ] `/healthz` → `{"status":"ok"}` (DB 조회 없음)
- [ ] `/readyz` → `{"status":"ok"}` (DB 연결 확인, 수동 1회)
- [ ] 관리자 Google 로그인 → 역할 '관리자' 표시
- [ ] 교수 로그인 → 상담 시간 등록 → 학생 테스트 계정으로 예약 → 취소
- [ ] 학생 계정으로 `/api/admin/users` 호출 → 403
- [ ] 응답 헤더에 CSP, HSTS, `X-Frame-Options` 포함
- [ ] 쿠키 `Secure; HttpOnly; SameSite=Lax`
- [ ] `/docs` 비노출(운영)
- [ ] 개발 로그인 `/auth/dev/login` → 404

### Unified booking deadline and historical unresolved appointments (0010)

- `booking_deadline_minutes` is the single student deadline for booking, cancellation,
  and rescheduling (default 30 minutes). Exactly 30 minutes before is allowed; one
  second later is not. Rescheduling must meet the deadline for **both the original
  and new appointment**. Staff overrides remain unchanged.
- Existing explicit minute settings take precedence, followed by non-default legacy
  `booking_deadline_hours`, then the 30-minute default. Retired
  `cancel_deadline_hours` values remain stored for history but no longer govern a
  separate policy. Old clients submitting conflicting cancellation values receive
  a validation error instead of silently restoring a three-hour policy. The policy
  response retains legacy hour aliases derived from the unified minute value.
- Migration 0010 only expands the booking status constraint. It does not change
  bookings. However, **starting the new app** makes the completion worker classify
  still-booked appointments ending on/before the persisted auto-completion activation
  marker as `expired` (기간 종료·결과 미확인). This is a deliberate data transition,
  not a claim of attendance or absence; obtain explicit approval before deployment.
  Existing IDs, notes, event history, slots and notification history remain intact.
  Each changed booking receives one `booking.expired` audit entry. No cancellation
  or completion notification is sent for this housekeeping transition.
- This releases the student's one-active-booking constraint without deleting history.
  Professors/admins can filter the booking list by 결과 미확인 (includes past dates)
  and explicitly record completed/no-show after checking the actual outcome. The
  unresolved state is excluded from the completed/no-show rate denominator.
- Before an approved deployment: confirm current affected counts and activation
  marker using a read-only aggregate, retain a recoverable database backup, run
  PostgreSQL migration and regression CI, then apply schema and start the app.
  Check aggregate unresolved counts and a read-only health/readiness smoke test.
  Never log private notes or student identifiers during these checks.
- Rollback: do not downgrade schema while `expired` rows exist. The downgrade guard
  refuses to invent outcomes or reactivate old bookings. Keep the expanded schema
  and deploy a compatible forward fix; do not roll back to code that cannot display
  unresolved appointments. SQLite migration rebuilds in an explicit transaction,
  validates foreign keys before commit, and restores FK enforcement afterward.

### In-place rescheduling

- A reschedule now keeps the booking ID, original creation metadata, private note,
  applicant details, and prior event history. Only its slot and update timestamp
  change. One `rescheduled` event captures the before/after slot IDs, time ranges,
  types and truncated locations. Old cross-ID `rescheduled_from/to` events remain
  readable; existing records are not rewritten or merged.
- Slot capacities and the same booking update commit in one transaction. A failed
  capacity check, stale client view, or outbox failure preserves the original
  booking, both seat counts, event history and notification queue. Booking and
  ordered slot locks serialize transfers; database deadlocks produce the existing
  retryable conflict response rather than partial changes.
- Current clients send `expected_slot_id` to reject stale edits. Legacy clients
  without it retain compatibility, with row-lock serialization and full history.
- Student edits require both original and target starts to be at least the unified
  30-minute deadline away (exact boundary allowed). The maximum booking horizon
  applies only to new reservations, not edits. Only open slots with free capacity
  may be selected; staff overrides remain unchanged.
- The outbox receives a single `changed` event with the same booking ID and chain,
  and before/after time snapshots. No separate cancellation or creation notice is
  generated. Reminder/automatic-completion wake scheduling remains unchanged.
- This change requires no schema migration or data backfill. Existing historical
  cancellations, completions and unresolved records are retained as-is.

## Professor app inbox and suggestion notices

Migration 0011 only adds the per-professor inbox table; no historical records are
reclassified or backfilled. Booking event notices persist atomically even when
external channels are disabled or no push device is registered. The app inbox
is refreshed on opening or explicit refresh, not by background polling. New
suggestions use content-free notices delayed randomly 5–10 minutes; no author,
suggestion ID or text is retained in notices. Timing anonymity is limited as
explained in anonymity.md. Existing push opt-in and valid-session checks remain;
Android Chrome is the supported push provider. External provider acceptance is
not proof that a phone received/read a notification. Old suggestions are not resent.

Rollback retains schema 0011 and its inbox records; do not downgrade after notices
exist. Previous application code is compatible with the additive table. No live
student reservation or suggestion may be created for release verification.

## Staff notification bell

Professor and administrator accounts receive their own app-inbox rows for new
booking/suggestion events. The header bell shows the signed-in account's unread
count and opens a compact preview; the full inbox supports read marking. Students
cannot access staff inbox routes. Existing mobile More navigation remains available.
External suggestion push/email eligibility is unchanged (professor-only); this
release expands only the app inbox and never registers devices or changes opt-in.
No migration or historical backfill is performed. Notification UI fetches on boot,
explicit opening/refresh and read changes, not on an interval. Delayed suggestion
availability remains 5–10 minutes and unread counts exclude not-yet-due records.
