# ClassBridge 스테이징 운영·유지보수 절차

> 대상: Render classbridge-staging + Neon ClassBridge/staging + GitHub seojb1204/ClassBridge.
> 운영 테스트는 가상 데이터 한정. **실제 학생에게 배포하거나 데이터를 수집하기 전에는 정책·보안 승인이 필요**하다.
> 작성 시점: 2026-11-03. 실행한 작업과 아직 검증되지 않은 항목을 구분한다.

## 0. 기준 환경 (작업 시작 전 반드시 재확인)

- GitHub 원본 기획/기능: PR #1 / feature/classbridge-v1
- 후속 구현: PR #2 / fix/gpt-prelaunch-improvements-20261103
- 운영 강화 격리 작업: chore/classbridge-maintenance-hardening-20261103
- Render 서비스: https://dashboard.render.com/web/srv-dbks45p5efls73fgucjg
- 현재 배포 서비스 URL: https://classbridge-staging.onrender.com
- Neon: project `little-waterfall-57700021`, staging branch `br-mute-bird-azdm6hbl`
- Neon `production` 브랜치는 유지하고 **staging 실수로 production에 연결하지 말 것**.
- 코드/DB의 실제 현재 상태는 매번 다시 조회한다. 이 문서의 날짜가 지난 뒤에도 위 상태가 동일하다고 가정하지 않는다.

## 1. 변경 관리 (사용자 승인과 AI 검증)

1. 사용자 또는 교수자가 재현 절차·기대 동작·현재 동작을 제시하거나 AI가 오류를 탐지한다.
2. AI는 GitHub diff, Render 배포 커밋/로그, Neon 브랜치·버전·접근 범위를 확인한다.
3. 배포 중인 브랜치를 덮어쓰지 않고 **별도 Git 브랜치**에서 수리한다.
4. 인수 기준을 테스트로 정하고 SQLite+PostgreSQL+E2E 테스트를 실제 실행한다.
5. CI(Ruff, pip-audit, pytest, Playwright) 통과를 확인한다. 미실행 항목은 성공으로 표시하지 않는다.
6. 변경 내역과 검증 근거를 PR에 보존한다. 유료전환·주요 권한 정책·개인정보 저장·데이터 삭제·DB 마이그레이션·배포 등 고위험 변경은 사전 승인받는다.
7. **Auto-Deploy를 Off로 설정한 뒤**, 승인된 커밋만 수동 배포한다. Render의 환경변수 변경도 재배포를 트리거할 수 있어 사전에 확인한다.
8. 배포 후 /healthz 및 실제 역할별 흐름을 검증한다. 실패하면 가장 최근 정상 커밋과 DB 변경의 호환성을 확인한 뒤 롤백한다.

## 2. 일일 감시

- 매일 자동화: Render 배포 상태, 비정상 종료/5xx 오류, Neon DB 접근·리소스 이상. 일반적인 무료 서버 휴면은 장애로 오인하지 않는다.
- 사람이 로그인한 상태에서 `/healthz` 또는 백엔드 로그를 확인할 때 개인정보/토큰이 포함된 로그를 복사·공유하지 않는다.
- 점검 결과가 이상이면 서비스 URL·배포 ID·커밋 SHA·최초 오류 시각과 코드만 공유한다. 시크릿/연결 문자열은 숨긴다.
- 무료 플랜 휴면을 회피하기 위한 비정상적인 반복 호출을 만들지 않는다.

## 3. 주간 점검

- GitHub Dependabot/의존성 보안 검사와 PR/CI 실패 확인.
- 한 건의 스테이징 예약/취소/변경을 테스트 계정으로 재현.
- 관리자·교수자·학생 권한 확인: 학생은 /api/admin/* 및 교수 기능에 접근 불가, 교수자는 관리자 전용 설정 불가.
- 설문: 참여 사실만 중복 차단에 저장하고 응답과 식별 정보가 연결되지 않는지 확인. 소수 응답 보호 임계값 확인.
- 익명 건의: 텍스트 XSS 방어, 제출 제한, 제출자 ID 부재 확인.
- 익명 기능은 개인정보·익명성 승인 전 `FEATURE_SURVEYS=false`, `FEATURE_SUGGESTIONS=false` 유지.
- Render/Neon 무료 사용량, 컴퓨팅 시간, DB 저장공간, 네트워크 한도 확인.

## 4. 백업과 복구

- **실제 백업 파일이 생성되기 전까지 데이터 보호가 완료됐다고 보고하지 않는다.**
- Neon 무료에서 staging(비루트) 직접 수동 스냅샷 생성은 현재 지원하지 않는다는 오류가 관찰됐다. 다른 백업 방식이 필요하다.
- `scripts/backup_neon_encrypted.sh`: pg_dump의 표준 출력 → GPG 공개키 암호화로 저장. plaintext 덤프를 디스크에 남기지 않는다.
- 운영자가 PostgreSQL 클라이언트·GPG를 설치하고 별도 암호화 키를 준비해야 한다. `DATABASE_URL_DIRECT`는 터미널/시크릿 저장소에만 입력한다.
- 백업 실행 예시:
  ```bash
  export DATABASE_URL_DIRECT='(Neon staging direct URL — 화면/로그에 표시 금지)'
  export BACKUP_GPG_RECIPIENT='(암호화에 사용할 GPG 공개키 지문)'
  export BACKUP_DIR='(암호화 파일 보관 폴더)'
  bash scripts/backup_neon_encrypted.sh
  ```
- 실제 복원 테스트는 별도 **이름에 restore가 포함된 빈 테스트 DB**에서만 `scripts/verify_neon_restore.sh`로 수행. 기존 staging·production에 직접 복원하거나 `--clean`하지 않는다.
- 별도 DB 생성/복원은 저장소 비용·운영 DB 영향 확인 후 사전 승인하고 진행한다.
- 암호화 키를 잃으면 백업을 읽을 수 없다. 복구용 비밀키를 분리 보관하고 접근자를 최소화한다.
- 보관기간·저장 위치·자동 파기 여부는 **아직 사용자·교수자·학교 정책 미결정**이다. 임의 삭제·파기 스케줄을 실행하지 않는다.

## 5. 오류·장애 대응

| 증상 | 확인 | 우선 조치 |
|---|---|---|
| Render 5xx / crash | 최근 Deploys, Logs, commit | 가장 먼저 실패한 로그, env 누락, DB 접속 확인 |
| /healthz 503 | Neon staging 연결 및 무료 한도 | DB 연결 문자열 비밀값 비교, 무료 리소스 초과 여부 |
| Google 오류 400 | Google Auth Platform의 Redirect URI, OAuth 클라이언트 일치 | `https://classbridge-staging.onrender.com/auth/google/callback`을 정확히 등록 |
| 같은 이메일 409 | 개발용 계정과 Google sub 중복 | 승인된 스테이징 한정 계정 이전 코드 및 테스트 확인 |
| 예약 인원 초과 | PostgreSQL 예약·정원 불변 조건 | 조건부 업데이트·부분 유니크 인덱스 점검 |
| 상담 슬롯 시간 중복 | PostgreSQL GiST 제외 제약 | ex_slots_no_overlap_open 존재 확인 |
| 익명성 위험 | 응답 행·로그·DB 접근·저장 순서 | 익명 기능 끄고 개인정보 검토. 앱 관리자는 참여자별 응답을 볼 수 없도록 유지 |

## 6. 개인정보·익명성·학교 운영 필수 미결정

- 개인정보 처리의 법적 근거 및 실제 학생 동의 방식
- 수집·보존·삭제 기간과 학생별 삭제/정정 요청 대응
- 항공서비스학과 교수자·학교 운영 승인
- 외부 클라우드(Render, Neon, Google)에 학생정보 저장·처리에 대한 승인과 국외 이전 검토
- 익명 설문/건의의 재식별 한계(DB 로그, 물리 저장 순서, 낮은 응답 수)와 학생 안내문
- 인증은 개인 Gmail로 허용하며, Google 로그인만으로 실제 수강생 여부는 검증되지 않는다
- 운영 책임자, 복구 책임자, 백업 보관 위치, 이용자 문의처

위 사항을 확정하지 않은 채로 실학생 대상 공개 운영하지 않는다.

## 7. 운영 인수 기준

- GitHub CI 리포트(통과 테스트 수와 commit hash) 확보
- 관리자/교수자/학생 별 계정 로그인 및 접근 통제
- 개별/단체 상담 정원, 예약 변경·취소, 3시간 마감, 동시 요청 검사
- 익명 설문 제출 중복 차단·최소 응답수 보호, 건의 익명화 검증
- Render `/healthz` DB 정상 응답, 이전 배포 롤백 절차 확인
- **암호화 백업 실제 1회 + 격리된 DB 복원 성공 1회**는 아직 별도 실행 필요
- 정책 승인 후 공개 운영/유료 전환 여부 최종 결정
