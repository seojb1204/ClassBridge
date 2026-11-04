# ClassBridge 스테이징 운영 준비 점검 — 2026-11-04

## 확인한 현재 상태
- Render 서비스 `srv-dbks45p5efls73fgucjg`, Live SHA `057460f1b21a5632bd0947b188373afbf40ed49e`.
- Render 추적 브랜치는 아직 `fix/gpt-prelaunch-improvements-20261103`; Auto-Deploy는 Off.
- GitHub `staging` 브랜치는 위 Live SHA에서 분기해 만들었음. `main` 및 기존 미병합 PR #1, #2, #4, #3, #5는 유지.
- 신규 PR #6은 스테이징 허용 이메일 검사를 유효 세션에도 매 요청 시행하도록 보완. **미병합·미배포**, 기존 접근 중이던 비허용 계정은 적용 시 401을 받게 됨.
- Neon staging `br-mute-bird-azdm6hbl`, production `br-fragrant-cell-az98nx7s`는 분리해 유지. DB 스키마 `0004`; 중복 활성 예약/정원 오류 없음.

## 운영 배포 구조
1. 먼저 `staging`이 현재 Live SHA와 같음을 확인하고, Render Settings에서 추적 GitHub 브랜치를 `staging`으로 바꾸는 작업의 영향을 승인받는다.
2. Render Auto-Deploy **Off 유지**. 브랜치 변경이 새 배포를 시작할 수 있으므로 변경 전후 Deploys와 Live SHA를 확인.
3. `staging`에 추가된 새 코드는 GitHub CI 성공 후 수동 배포한다. 구버전 자동 재배포 방지.
4. 회귀 시 직전 정상 배포 `dep-dbldqg49v7es739o88ag` (SHA `057460f1`)로 복귀 가능 여부와 DB 호환성을 확인한다. `main` 병합·데이터 삭제는 별도 승인 없이 수행하지 않는다.

## 인증·권한 (실제 외부 검증 아직 미완료)
- Render 환경변수에서 `APP_ENV=production`, `STAGING_MODE=true`, `DEV_LOGIN_ENABLED=false`, `COOKIE_SECURE=true` 여부를 확인하되, **시크릿 값은 복사하거나 공유하지 않는다**.
- 실제 HTTPS `/api/auth/config`에서 `dev_login=false`를 확인. 현재 연결된 도구로는 외부 공개 응답을 독립 확인하지 못함.
- Google로 로그인한 학생·교수자·관리자의 역할별 접근을 검증한다. 학생은 교수자 상담 기록/통계/관리자 기능에 접근할 수 없어야 한다.
- 개인 Gmail 허용은 기존 정책이지만 실제 학교 수강 자격을 증명하지는 않음.

## 데이터 백업 (아직 미수행)
- Neon 스테이징 수동 스냅샷 **0개**, 자동 스냅샷 일정 **0개**.
- `scripts/backup_neon_encrypted.sh`는 `pg_dump`를 GPG 공개키로 암호화해 저장하도록 준비됐지만 실제 파일 생성/복구는 미검증.
- 암호화 공개키·비밀키 보관, 백업 파일 저장 위치/기간, 새 복원용 **격리 DB**와 비용을 승인받은 이후에만 실행.
- 기존 staging/prod DB에 복원하지 않으며, 계정/예약/슬롯 수 및 DB 제약을 복원 DB에서 확인.

## 시범 운영 사전 조건
- 교수 1명·관리자 1명·학생 3~5명은 우선 **가상 이름·학번**으로 상담 예약→변경→취소→기록 작성/조회/수정·통계를 점검.
- 실제 Android Chrome·iOS Safari와 PC에서 일간 시간표/목록 전환, 메뉴 터치 영역, 기록 접근 확인. Chromium E2E 성공과 별개로 평가.
- 익명 설문/건의 기능 비활성 유지. 실제 학생 데이터 수집, 보존/삭제 기간, 국외 클라우드 사용과 교수자/학교 승인이 끝나기 전 실학생 대상으로 공개 운영하지 않는다.
