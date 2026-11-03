# ClassBridge — Neon + Render 비공개 시험 환경 준비

> 목표: 인터넷에서 접속 가능하지만 **승인된 테스트 Google 계정만 로그인**하는 환경.
> 실제 학생 개인정보·실제 상담 기록을 사용하지 않는다.
> 생성·배포 전에 호스팅 제공자의 실제 비용을 확인하고 유료인 경우 사용자 승인을 받는다.

## 현재 확인된 구성

- GitHub: `seojb1204/ClassBridge` / `fix/gpt-prelaunch-improvements-20261103` (PR #2, 미병합)
- 애플리케이션: FastAPI · SQLAlchemy · Alembic · 정적 ES 모듈 UI
- DB: Neon 전용 `ClassBridge-staging` PostgreSQL 프로젝트 (아직 생성 전)
- 서버: Render 전용 `classbridge-staging` Web Service (아직 생성 전)
- 로그인: Google OAuth 외부 사용자 **Testing** 단계, 승인된 Gmail 계정만
- 기본 보안: `STAGING_MODE=true` + `STAGING_ALLOWED_EMAILS`, 운영용 구분 `APP_ENV=production`
- 운영 배포: 미실행

## 권한이 필요한 작업

1. **Neon 앱을 ChatGPT에 연결**하고 Neon 서비스 로그인을 승인한다. 완료되면 별도 Neon 프로젝트를 생성하고 비용을 확인할 수 있다.
2. **Render** 앱은 ChatGPT에서 작업 공간 조회가 가능하다. 신규 서비스는 Neon DB와 Google OAuth 정보를 준비한 다음 생성한다. 기존 `liar-game` 서비스에는 손대지 않는다.
3. **Google Cloud Console**은 ChatGPT에서 OAuth 클라이언트를 직접 발급하는 연결 기능이 없다. 사용자가 테스트용 Google Cloud 프로젝트와 OAuth Web application 인증 클라이언트를 만들어야 한다.
4. **최고 관리자·교수자·학생 테스트용 Gmail**을 준비한다. GitHub와 채팅에 비밀번호나 인증 시크릿을 남기지 않는다.

## 1. Neon 프로젝트 (무료 한도 전용)

1. `ClassBridge-staging`이라는 이름의 **독립 프로젝트**를 만든다. 무료 한도를 초과하는 비용이 표시되면 만들기 전에 멈춘다.
2. 가능한 경우 사용자와 가까운 지역인 **Tokyo (ap-northeast-1)** 등 지원되는 지역을 선택한다. 실제 지원 여부를 프로젝트 생성 화면에서 검증한다.
3. Connect에서 아래 두 종류의 연결 문자열을 준비한다. URL 자체는 암호를 포함하므로 공개 문서/채팅에 게시하지 않는다.
   - `DATABASE_URL`: **Pooled**, 애플리케이션 실행용
   - `DATABASE_URL_DIRECT`: **Direct**, Alembic DB 마이그레이션용
4. `sslmode=require` 및 공급자가 지정한 다른 보안 연결 옵션을 유지한다.
5. 신규 DB에만 `0001 → 0002 → 0003 → 0004` 마이그레이션을 적용한다. 이미 사용 중인 DB를 변경하지 않는다.
6. 상담 슬롯 겹침·예약 정원·권한 차단을 실제 PostgreSQL에서 확인한다.

## 2. Render 무료 Web Service

1. 새 Web Service를 `classbridge-staging`이라는 이름으로 생성한다.
2. GitHub 저장소는 `https://github.com/seojb1204/ClassBridge`; 브랜치는 `fix/gpt-prelaunch-improvements-20261103`.
3. Region: Singapore, Runtime: Python, Plan: Free(현재 제공되는 경우), `autoDeploy=no`.
4. Build: `pip install -r requirements.txt`
5. Start: `alembic upgrade head && uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT --proxy-headers`
6. 다음 값을 **Render의 Environment Variables에만** 입력한다.

| 이름 | 값 / 확인 |
|---|---|
| `APP_ENV` | `production` |
| `STAGING_MODE` | `true` |
| `STAGING_ALLOWED_EMAILS` | 승인된 관리자·교수자·학생 테스트 Gmail을 쉼표로 구분 |
| `DATABASE_URL` | Neon pooled URL (비밀) |
| `DATABASE_URL_DIRECT` | Neon direct URL (비밀) |
| `BASE_URL` | `https://<실제 Render 주소>` |
| `GOOGLE_CLIENT_ID` | Google에서 생성한 Client ID |
| `GOOGLE_CLIENT_SECRET` | Google에서 생성한 Client Secret (비밀) |
| `ADMIN_EMAILS` | 관리자용 테스트 Gmail |
| `PROFESSOR_EMAILS` | 교수자용 테스트 Gmail |
| `SECRET_KEY` | 최소 32자리 이상의 강한 무작위 값. Render 자동 생성 권장 |
| `COOKIE_SECURE` | `true` |
| `DEV_LOGIN_ENABLED` | `false` |
| `ALLOWED_EMAIL_DOMAINS` | 빈 값 (개인 Gmail 로그인 유지) |
| `FEATURE_SURVEYS` | `false` |
| `FEATURE_SUGGESTIONS` | `false` |
| `AI_MODE` | `disabled` |

> 서비스 URL은 인터넷에 공개될 수 있다. 이는 VPN/사설 네트워크가 아니라 **로그인 허용 목록으로 제한하는 스테이징**이다. OAuth 설정 전에는 기능 확인을 위한 실제 배포가 완료되지 않는다.

## 3. Google OAuth 설정 (사용자 직접 승인 필요)

1. Google Cloud Console에서 테스트 전용 프로젝트를 만들거나 선택한다.
2. Google Auth Platform의 사용자 유형은 External(외부), 게시 상태는 Testing(테스트)을 선택한다.
3. 테스트 관리자·교수자·학생 Gmail을 **Test users**에 등록한다.
4. OAuth Client ID 유형은 Web application을 선택한다.
5. 승인된 Redirect URI에 `https://<실제 Render 주소>/auth/google/callback`을 등록한다.
6. Client ID/Secret을 Render Environment에 등록한다. **채팅·PR·GitHub에는 시크릿을 남기지 않는다.**

## 4. 배포 후 수용 기준

- [ ] Render의 `/healthz`가 DB 연결까지 정상 응답
- [ ] 비허용 Google 계정 로그인 거부
- [ ] 관리자·교수자·학생 테스트 계정의 실제 Google 로그인 성공
- [ ] 관리자=교수자 모든 권한+계정·역할·설정 관리 권한
- [ ] 학생용 주간/일별 상담 시간표와 3시간 전 취소 제한
- [ ] 학생 신청 정보·대면/온라인/상담 유형·교수자 화면 반영
- [ ] 동시 예약/중복 상담 슬롯 거부, PostgreSQL 전체 제약 검증
- [ ] 개인정보 보유기간·익명성·운영 승인 미완료이므로 **실제 학생 대상 공개하지 않음**

참고:
- https://neon.com/docs/get-started/connect-neon
- https://render.com/docs/your-first-deploy
- https://developers.google.com/identity/protocols/oauth2/web-server
