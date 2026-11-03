# ClassBridge 비공개 테스트 환경 — 연결 체크리스트

> 목적: 가상 데이터로만 Render + Supabase PostgreSQL + Google 로그인 흐름을 시험한다.
> 이 문서는 사용자 계정 설정을 안내한다. 이 파일 자체로 어떤 외부 서비스도 생성·배포되지 않는다.

## 시작 조건

- GitHub 소스: `seojb1204/ClassBridge`, 테스트 브랜치 `fix/gpt-prelaunch-improvements-20261103` (PR #2).
- PR #2의 통과한 CI 결과를 확인하고, 코드/설정 변경 후 다시 검사한다.
- **기존 다른 Supabase 프로젝트를 재사용하거나 데이터베이스를 변경하지 않는다.**
- 데이터베이스와 웹서비스의 새 비용이 발생한다면 서비스 생성 전에 승인을 받는다.
- 학생 개인정보 사용·공개 운영·운영 데이터 삭제는 별도로 승인받는다.

## 1. Supabase — 사용자가 조직을 지정하면 GPT가 진행 가능한 작업

1. 서비스용 **별도 프로젝트** `ClassBridge-staging` 생성 대상 조직을 사용자에게 확인한다.
2. 해당 조직의 프로젝트 비용을 확인하고 유료인 경우 사용자의 명시적 승인을 받는다.
3. 사용자의 승인이 확보되면 프로젝트 리전을 **Seoul (ap-northeast-2)**로 지정한다.
4. 기존 프로젝트는 수정하지 않는다.
5. 새 프로젝트에만 Alembic 마이그레이션 `0001 → 0002 → 0003 → 0004`를 검토·적용한다.
6. 새로운 `0003` 제약은 겹치는 열린 슬롯이 존재하면 실패하며, 기존 데이터를 삭제하지 않는다.
7. 보안 검증: Data API 접근 권한과 RLS 상태, anon/authenticated 접근 거부 여부를 새 DB에서 확인한다.
8. 데이터베이스의 인증 정보는 Render 비밀 환경변수에만 입력한다. GitHub와 채팅에 평문으로 저장하지 않는다.

## 2. Render — 계정 승인 후

1. Render 계정을 연결하고 GitHub 저장소 접근 권한을 허용한다.
2. `New → Blueprint`를 선택하고 `seojb1204/ClassBridge` 저장소를 연결한다.
3. **`main` 대신 브랜치 `fix/gpt-prelaunch-improvements-20261103`를 선택**한다.
4. 저장소 루트의 `render.yaml`을 사용한다. 서비스 요금제는 사용자가 승인한 뒤 선택한다.
5. 설정에서 `autoDeploy`가 꺼져 있는지 확인한다. 명시 승인 없이 자동 배포하지 않는다.
6. 서비스 생성 후 할당되는 실제 HTTPS 주소를 확인하고 아래 Google OAuth 설정에 사용한다.
7. `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 등 민감 값은 Render Environment에만 저장한다.

## 3. Google OAuth — 사용자가 브라우저에서 수행해야 하는 절차

1. https://console.cloud.google.com/apis/credentials 에서 별도 테스트용 Cloud 프로젝트를 만들거나 선택한다.
2. Google Auth Platform의 브랜딩과 대상(External)을 설정한다.
3. 테스트 상태에서 **실제로 로그인할 테스트용 Gmail 계정만** 테스트 사용자로 추가한다. 실제 학생 계정은 등록하지 않는다.
4. OAuth 클라이언트 유형을 **Web application**으로 생성한다.
5. 승인된 리디렉션 URI에 `https://<Render 서비스의 실제 주소>/auth/google/callback`을 정확히 등록한다.
6. 클라이언트 ID와 보안 비밀값은 Render Environment에 입력한다. 값을 이 채팅이나 저장소에 게시하지 않는다.
7. Google 로그인이 정상 동작하는지 관리자·교수자·가상 학생 계정 각각으로 확인한다.

## 4. Render 필수 환경변수 점검

```text
APP_ENV=production
COOKIE_SECURE=true
DATABASE_URL=(새 스테이징 PostgreSQL 연결 문자열, 비밀)
BASE_URL=https://(실제 Render 서비스 주소)
GOOGLE_CLIENT_ID=(비밀 환경변수)
GOOGLE_CLIENT_SECRET=(비밀 환경변수)
ADMIN_EMAILS=(테스트 관리자 계정 이메일)
PROFESSOR_EMAILS=(테스트 교수자 계정 이메일)
ALLOWED_EMAIL_DOMAINS=(빈 값; 개인 Gmail 허용)
FEATURE_SURVEYS=false
FEATURE_SUGGESTIONS=false
AI_MODE=disabled
DEV_LOGIN_ENABLED=false
SECRET_KEY=(Render의 generateValue 사용)
```

주의: Render의 무료 웹서비스 주소도 일반 인터넷에서 접근 가능한 주소다. '**비공개 테스트**'란 브라우저 접속 자체가 차단된다는 뜻이 아니라 테스트 승인 계정만 로그인하고 가상 데이터만 사용한다는 운영 수준이다. 실제 비공개 네트워크 격리가 필요하면 별도 인프라 설계를 승인받는다.

## 5. 완료 확인

- `/healthz`가 정상이고 운영 DB 연결에 성공한다.
- 실제 Google 로그인(관리자/교수자/학생)이 성공하고 권한 분리를 확인한다.
- 학생이 시간표 예약→조회→취소·변경을 완료한다.
- 관리자·교수자의 예약 관리 및 상담 기록 접근을 확인한다.
- PostgreSQL에서 동시 예약과 겹치는 시간 등록을 거부한다.
- 모바일 브라우저에서 주간/일별 예약 UI를 확인한다.
- 익명 설문·건의함은 별도 개인정보·익명성 검토를 통과하기 전까지 운영 환경에서 켜지 않는다.
- 실학생 대상 공개, 유료 결제, 운영 데이터 수정은 아직 수행하지 않는다.

공식 문서:
- Render Blueprint: https://render.com/docs/infrastructure-as-code
- Render 환경변수: https://render.com/docs/configure-environment-variables
- Google OAuth Web server: https://developers.google.com/identity/protocols/oauth2/web-server
- Supabase 요금: https://supabase.com/docs/guides/platform/billing-on-supabase
