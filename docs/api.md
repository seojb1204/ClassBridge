# API 명세

> `scripts/gen_api_doc.py`로 코드에서 자동 생성. 상세 스키마는 `docs/openapi.json` 또는 개발 서버 `/docs`.

모든 변경 요청(POST/PUT/PATCH/DELETE)에는 `X-CSRF-Token` 헤더가 필요합니다 (`GET /api/me`의 `csrf_token`).
오류 응답 형식: `{"error": "코드", "message": "설명"}`

| 메서드 | 경로 | 필요 권한 | 설명 |
|---|---|---|---|
| GET | `/` | - | 웹 화면 |
| GET | `/api/admin/audit` | audit:view | 관리 작업 이력 조회 |
| GET | `/api/admin/settings` | settings:manage | 운영 설정 조회 |
| PUT | `/api/admin/settings` | settings:manage | 운영 설정 변경 |
| GET | `/api/admin/users` | user:manage | 사용자 목록 |
| PUT | `/api/admin/users/{user_id}/active` | user:manage | 계정 활성/비활성 |
| PUT | `/api/admin/users/{user_id}/role` | role:manage | 역할 변경 (자기 자신·마지막 관리자 불가) |
| POST | `/api/analysis` | ai:analyze | 의견 분석 (로컬/외부 AI) |
| GET | `/api/auth/config` | 공개 | 로그인 화면용 공개 정보 (비밀 없음). |
| GET | `/api/blackouts` | slot:view | 상담 불가일 목록 |
| POST | `/api/blackouts` | slot:manage | 상담 불가일 등록 |
| DELETE | `/api/blackouts/{blackout_id}` | slot:manage | 상담 불가일 삭제 |
| GET | `/api/bookings` | booking:manage | 예약 현황 조회 |
| POST | `/api/bookings` | slot:view | 예약 생성 (student_id는 교수자·관리자만) |
| GET | `/api/bookings/mine` | booking:self | 내 예약 목록 (상담 기록 제외) |
| POST | `/api/bookings/{booking_id}/cancel` | slot:view | 예약 취소 (학생: 3시간 전까지, 교수자: 사유 필수) |
| GET | `/api/bookings/{booking_id}/history` | booking:manage | 예약 변경 이력 |
| PUT | `/api/bookings/{booking_id}/note` | booking:note | 상담 기록 저장 |
| POST | `/api/bookings/{booking_id}/outcome` | booking:manage | 완료/미참석 처리 |
| POST | `/api/bookings/{booking_id}/reschedule` | slot:view | 예약 변경 (원자적, 실패 시 기존 예약 유지) |
| GET | `/api/me` | login | 현재 사용자·권한·CSRF 토큰 |
| GET | `/api/slots` | slot:view | 상담 시간표 조회 |
| POST | `/api/slots` | slot:manage | 상담 시간 일괄 생성 (반복·휴식·휴무일 제외) |
| PATCH | `/api/slots/{slot_id}` | slot:manage | 상담 시간 수정 (정원 축소 제한) |
| POST | `/api/slots/{slot_id}/cancel` | slot:manage | 상담 시간 취소 (예약 있으면 force+사유) |
| GET | `/api/students` | booking:manage | 대리 예약용 학생 목록 |
| GET | `/api/suggestions` | suggestion:read | 건의 목록 |
| POST | `/api/suggestions` | suggestion:submit | 익명 제출 |
| GET | `/api/suggestions/stats` | suggestion:read | 건의 통계 |
| PUT | `/api/suggestions/{suggestion_id}/status` | suggestion:read | 건의 상태 변경 |
| GET | `/api/surveys` | survey:manage | 설문 목록 (응답 수 포함) |
| POST | `/api/surveys` | survey:manage | 설문 생성 (초안) |
| GET | `/api/surveys/student/list` | survey:respond | 학생용 설문 목록 (본인 참여 여부) |
| GET | `/api/surveys/student/{survey_id}` | survey:respond | 학생용 설문 상세 |
| DELETE | `/api/surveys/{survey_id}` | survey:manage | 초안 삭제 |
| GET | `/api/surveys/{survey_id}` | survey:manage | 설문 상세 |
| PATCH | `/api/surveys/{survey_id}` | survey:manage | 설문 수정 (게시 후 문항 잠금) |
| POST | `/api/surveys/{survey_id}/close` | survey:manage | 설문 종료 |
| POST | `/api/surveys/{survey_id}/duplicate` | survey:manage | 설문 복제 (새 버전) |
| GET | `/api/surveys/{survey_id}/export.xlsx` | data:export | 엑셀 다운로드 (수식 주입 방어) |
| POST | `/api/surveys/{survey_id}/publish` | survey:manage | 설문 게시 |
| POST | `/api/surveys/{survey_id}/responses` | survey:respond | 익명 제출 |
| GET | `/api/surveys/{survey_id}/results` | survey:results | 설문 결과 (최소 응답 수 미만이면 숨김) |
| POST | `/auth/dev/login` | - | 개발용 로그인 (운영 불가) |
| GET | `/auth/google/callback` | - | Google 로그인 콜백 |
| GET | `/auth/google/login` | - | Google 로그인 시작 |
| POST | `/auth/logout` | login | 로그아웃 |
| GET | `/healthz` | - | 상태 확인 |
