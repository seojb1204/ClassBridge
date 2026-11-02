# 테스트 보고서

- 실행일: 2026-11-02 (KST)
- 환경: Python 3.13, SQLite 3, **PostgreSQL 16.15**, Chromium (Playwright 1.63)
- 명령:
  ```bash
  TEST_PG_URL=postgresql+psycopg://postgres@127.0.0.1:5433/classbridge_test RUN_E2E=1 \
    pytest -q -rs --junitxml=test-results.xml
  ruff check app tests migrations scripts
  pip-audit -r requirements.txt
  ```
- 결과: **113개 전부 통과** (unit 29 · integration 67 · PostgreSQL 9 · E2E 8), 건너뜀 0. ruff 통과, pip-audit에서 알려진 취약점 0건
- 테스트별 표: [test-results-table.md](test-results-table.md) (테스트 이름, 검증 요구사항, 결과, 시간)
- 화면 증거: [screens/](screens/) (PC 10장, 모바일 6장, E2E 실행 중 자동 캡처)

통과한 테스트는 기대 결과와 실제 결과가 같다는 뜻이다. 각 테스트의 기대값은 테스트 코드의 `assert`에 있다.

## 1. 검증 수준 구분

| 구분 | 항목 |
|---|---|
| **자동 테스트로 검증됨** | 권한 매트릭스와 기본 거부, 세션 무효화, CSRF, 보안 헤더·쿠키, 예약 정책 전부(§3.3·3.4), 설문 상태·검증·임계값·엑셀 수식 주입, 익명 스키마·로그 차단, 건의 속도 제한, 로컬 분석, AI 전송 데이터 필터, 마이그레이션(SQLite·PG 양방향) |
| **실제 PostgreSQL로 검증됨** | 동시 마지막 자리(12명 경쟁 → 1명), 단체 정원(20명 → 5명), 동일 학생 6중 예약 → 1건, 변경과 신규 예약 경쟁, 설문 8중 제출 → 1건, 관리자 상호 동시 강등(교착 없음, 관리자 1명 이상 유지), CHECK 제약. **5회 반복 실행 모두 통과** |
| **실제 브라우저로 검증됨 (Chromium)** | PC 1366×900, 모바일 390×844에서 학생 예약→조회→취소, 중복 클릭, 교수 완료 처리, 관리자 권한 변경, 설문 생성→미리보기→게시→응답→통계, 건의 제출→열람(HTML 미해석), 모바일 가로 스크롤 없음, 터치 버튼 높이 40px 이상. **6회 반복 실행 모두 통과** |
| **구현됐지만 검증 부족** | 실제 Google 로그인(가짜 검증기로 흐름만 검증, Google 서버와 실제 ID 토큰 미검증) · 외부 AI 실제 호출(모의 객체만) · Supabase GRANT/REVOKE SQL · Render 배포 · iOS Safari/Android 실기기 · HSTS(운영 모드에서만 켜짐) · 부하 테스트 |
| **미구현** | 개인정보 보유기간 경과 시 자동 파기(기간 미확정) · 이메일·알림 발송 · 앱 자체 관리자 MFA(Google 2단계 인증에 의존) · 앱 내 백업 버튼(문서화된 `pg_dump` 절차로 대체) |

## 2. 동시성 테스트가 실제로 결함을 잡는지 확인 (변이 검증)

원자적 좌석 차감을 "읽고-검사-쓰기" 방식(흔한 버그 패턴)으로 일부러 바꾸고 PostgreSQL 경쟁 테스트를 실행했다.

```
>       assert results.count("ok") == 1, results
E       assert 12 == 1          ← 1인 정원에 12명 모두 '예약 성공'
>       assert results.count("ok") == 5, results
E       assert 20 == 5          ← 5인 정원에 20명 성공
2 failed
```

원래 코드로 되돌리면 통과한다. 즉 이 테스트들은 의미 없이 통과하는 테스트가 아니다. (CHECK 제약만으로는 "갱신 손실"을 막지 못한다는 것도 이 실험에서 확인했다.)

## 3. 개발 중 실패 → 원인 → 수정 → 재실행 기록

| # | 실패한 테스트 | 원인 | 수정 | 재실행 |
|---|---|---|---|---|
| 1 | `test_capacity_cannot_drop_below_booked` (409 기대, 400 반환) | **코드 결함**: 단체 상담 정원 검증(최소 2명)을 "현재 예약 인원보다 작음" 검사보다 먼저 해서, 원인을 잘못 안내함 | `booking_service.update_slot` 검사 순서 변경 | 통과 |
| 2 | `test_blackout_blocks_generation_and_booking` | 테스트 결함: 반복 시작일이 과거 날짜 | 테스트 날짜 수정. 이 테스트는 예약이 아니라 생성 차단만 검증하므로 이름도 `..._slot_generation`으로 정정 | 통과 |
| 3 | E2E 관리자 역할 변경 (토스트 대기 시간 초과) | 테스트 선택자 `text=변경`이 모달 제목 "역할 변경"을 클릭함 | 모달 버튼은 정확한 텍스트의 `button`으로 선택 | 통과 |
| 4 | E2E 간헐 실패 (6회 중 2~3회) | 로그인 직후 홈 리디렉션이 테스트의 화면 이동보다 늦게 실행되는 경쟁 | 라우터에 렌더링 완료 표시(`body[data-ready]`)를 추가하고 테스트가 이를 기다리게 함 | 6/6 통과 |
| 5 | E2E 대기 함수 `EvalError` | CSP(`script-src 'self'`)가 테스트의 문자열 eval을 차단. **CSP가 실제로 작동한다는 증거** | eval 대신 속성 선택자로 대기 | 통과 |

## 4. 아키텍처 검증

- 순환 import: 없음 (AST 분석)
- 계층 간 역방향 의존: infra와 services가 서로를 참조하던 문제를 발견해, 공용 타입을 `core/identity.py`로 옮겨 해소함
- 권한 선언이 없는 `/api` 라우트: 0개 (공개 1개는 명시적 예외)
