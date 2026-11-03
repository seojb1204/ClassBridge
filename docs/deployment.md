# 배포 · 운영 가이드 (Render + Supabase + Google OAuth)

> 이 문서의 절차는 **실제 계정에서 실행해 검증하지 않았다**. 유료 결제, 공개 배포, 실제 학생 데이터 입력은 사용자 승인과 개인정보 검토가 끝난 뒤에 진행한다.

## 0. 구성 검토

| 구성 | 선택 | 근거 / 주의 |
|---|---|---|
| 웹 서버 | Render Web Service | FastAPI를 그대로 실행, `render.yaml` 제공. **무료 플랜은 15분간 요청이 없으면 휴면**해서 첫 접속이 수십 초 걸릴 수 있다. 수업 중 사용이 잦다면 유료 플랜(월 7달러 수준, 가격은 직접 확인)을 검토한다. |
| DB | Supabase PostgreSQL | 무료 플랜은 장기간 미사용 시 프로젝트가 일시중지되고, 무료 플랜에는 자동 백업(PITR)이 없다. 아래 수동 백업이 필수다. |
| 인증 | Google Cloud OAuth (OIDC) | 무료. 외부 사용자 대상이면 OAuth 동의 화면 게시가 필요하다. |
| CI | GitHub Actions | `.github/workflows/ci.yml` (PostgreSQL 서비스와 E2E 포함) |

단일 인스턴스를 전제로 한다. 요청 제한이 메모리 기반이라 인스턴스를 여러 대로 늘리면 Redis 같은 공유 저장소로 바꿔야 한다.

## 1. 환경 분리

| 환경 | APP_ENV | DB | 로그인 |
|---|---|---|---|
| 개발 | development | SQLite 파일 | 개발용 이메일 로그인 |
| 테스트/CI | test | SQLite + PostgreSQL(CI 서비스) | 개발용 로그인 / 가짜 검증기 |
| 비공개 스테이징 | production | 별도 Supabase 프로젝트 | Google (테스트 사용자만) |
| 운영 | production | 운영 Supabase | Google |

`APP_ENV=production`에서는 다음 중 하나라도 해당하면 **서버가 시작을 거부한다**: 개발 로그인이 켜져 있음, SECRET_KEY가 짧음, `COOKIE_SECURE=false`, SQLite, Google 키 없음, `ADMIN_EMAILS` 없음(`app/config.py`).

## 2. Google OAuth 설정

1. Google Cloud Console → 새 프로젝트 → "API 및 서비스" → "OAuth 동의 화면"
   - 사용자 유형: 외부(학교 Workspace라면 내부)
   - 범위: `openid`, `email`, `profile`만
   - 테스트 단계에서는 "테스트 사용자"에 관리자와 교수 계정만 추가
2. "사용자 인증 정보" → "OAuth 클라이언트 ID" → 웹 애플리케이션
   - 승인된 리디렉션 URI: `https://<도메인>/auth/google/callback`
3. 발급된 ID와 시크릿을 Render 환경변수 `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`에 넣는다(코드나 Git에는 넣지 않는다).
4. `ALLOWED_EMAIL_DOMAINS`에 학교 도메인을 넣어 외부 계정의 학생 가입을 막는다.

## 3. Supabase 설정

1. 프로젝트 생성(리전: Northeast Asia (Seoul)).
2. 상단 **Connect** 버튼 → **Session pooler** 연결 문자열(`...pooler.supabase.com:5432/postgres`)을 복사해 `[YOUR-PASSWORD]`를 바꾼 뒤 Render `DATABASE_URL`에 넣는다.
   - **Direct connection은 사용 불가**: Supabase의 직접 연결은 IPv6 전용인데(유료 IPv4 애드온 제외) Render는 외부로 IPv6 연결을 지원하지 않는다.
   - Transaction pooler(6543)는 쓰지 않는다: psycopg의 자동 prepared statement와 충돌할 수 있다.
3. 공개 API 경로 차단은 **배포 시 마이그레이션 `0002`가 자동으로 처리한다**. 첫 배포가 성공한 뒤 SQL Editor에서 아래 확인 쿼리를 실행해, 두 결과가 모두 `0`이면 정상이다.
   ```sql
   -- RLS가 꺼진 public 테이블 수 (0이어야 정상)
   SELECT count(*) FROM pg_tables WHERE schemaname='public' AND NOT rowsecurity;
   -- anon이 SELECT할 수 있는 public 테이블 수 (0이어야 정상)
   SELECT count(*) FROM pg_tables WHERE schemaname='public'
     AND has_table_privilege('anon', format('public.%I', tablename), 'SELECT');
   ```
   Supabase 대시보드의 **Advisors → Security Advisor**에서 "RLS disabled" 경고가 없는지도 확인한다.
4. 대시보드 멤버는 관리자 1명만 둔다(익명성 한계 L1·L2 완화).

## 4. Render 배포

1. Render → New → Blueprint → 이 저장소 선택(`render.yaml`), 또는 Web Service를 수동 생성
2. 환경변수 입력 (`.env.example` 참고): `BASE_URL=https://<서비스>.onrender.com`, `ADMIN_EMAILS`, `PROFESSOR_EMAILS`
3. 배포하면 시작 명령에서 `alembic upgrade head`를 실행한 뒤 서버를 띄우고 `/healthz`를 확인한다. 마이그레이션이 실패하면 서버가 뜨지 않아 새 버전이 실패 처리되고, 이전 버전이 계속 서비스된다.
4. 사용자 지정 도메인은 Render → Custom Domains에서 연결하고 HTTPS 인증서를 자동 발급받는다. `BASE_URL`과 Google 리디렉션 URI도 함께 바꾼다.

## 5. 관리자 초기 등록

1. `ADMIN_EMAILS`에 최고 관리자 이메일, `PROFESSOR_EMAILS`에 교수 이메일을 넣는다.
2. 두 사람이 Google로 처음 로그인하면 역할이 자동 부여되고 감사 로그(`user.bootstrap_role`)에 남는다.
3. 이후 역할은 앱의 "계정·권한" 화면에서만 바꾼다(환경변수는 신규 계정에만 적용).
4. 관리자 계정에는 Google 2단계 인증을 반드시 켠다(앱 자체 MFA는 없음, Google 계정 보안에 의존).

## 6. 로그 · 모니터링

- Render Logs: 애플리케이션 오류. 익명 제출 경로의 접근 로그는 앱에서 걸러지지만, Render 엣지 로그는 별도로 남는다(익명성 문서 L3).
- `/healthz`: DB 연결까지 확인한다. 외부 업타임 모니터(UptimeRobot 등)를 붙이면 무료 플랜의 휴면도 일부 줄일 수 있다(약관 확인).
- DB 장애 시 API는 503 `db_unavailable`을 반환한다.

## 7. 백업 · 복구

```bash
# 백업 (매주 + 학기 중요 시점, 암호화 저장소에 보관)
pg_dump "$DATABASE_URL" --format=custom --no-owner --file=classbridge-$(date +%Y%m%d).dump

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
| 503 db_unavailable | Supabase 상태, 프로젝트 일시중지 여부 | Supabase에서 재개, 연결 문자열과 비밀번호 확인 |
| 로그인 실패 (state 불일치) | 쿠키 차단, BASE_URL 불일치 | `BASE_URL`과 리디렉션 URI 일치 확인 |
| 서버 시작 실패 ConfigError | Render 로그 메시지 | 메시지에 나온 환경변수 수정 |
| 관리자 계정 분실 | 활성 관리자 0명? | `ADMIN_EMAILS`에 새 관리자 이메일 추가 → 해당 계정으로 로그인하면 자동 복구 |
| AI 분석 실패 | 외부 API 상태 | 자동으로 로컬 분석으로 대체됨. 기본 기능은 영향 없음 |

## 10. 배포 후 점검 (스모크 테스트)

- [ ] `/healthz` → `{"status":"ok"}`
- [ ] 관리자 Google 로그인 → 역할 '관리자' 표시
- [ ] 교수 로그인 → 상담 시간 등록 → 학생 테스트 계정으로 예약 → 취소
- [ ] 학생 계정으로 `/api/admin/users` 호출 → 403
- [ ] 응답 헤더에 CSP, HSTS, `X-Frame-Options` 포함
- [ ] 쿠키 `Secure; HttpOnly; SameSite=Lax`
- [ ] `/docs` 비노출(운영)
- [ ] 개발 로그인 `/auth/dev/login` → 404
