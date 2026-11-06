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
| POST | `/api/slots` | slot:manage | 상담 시간 일괄 생성 (반복·휴식) |
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

상담 불가일 API는 2026-11-05에 제거했습니다(404). 예약 가능 여부는 등록된 상담 시간, 정원, 예약 정책으로 결정합니다. 이전 클라이언트 응답 호환을 위한 `skipped_blackout_days`는 빈 배열입니다.
## 예약 화면 대표 공지

`GET /api/announcement`: 로그인한 사용자(slot:view). 학생에게는 게시 중인 공지의 제목·내용·수정 시각만 반환하며 숨김 상태이면 null입니다. 교수자·관리자는 초안과 버전도 조회합니다.

`PUT /api/announcement`: 교수자·관리자(announcement:manage), CSRF 필수. title(최대 100자), body(최대 2,000자), published, revision을 보냅니다. 게시 시 빈 제목·본문은 422, 오래된 버전으로 수정하면 409입니다. 일반 운영 설정 수정 권한은 부여하지 않습니다.

기존 app_settings의 booking_announcement 항목에 대표 공지 1개를 저장합니다. 새 테이블·마이그레이션은 없습니다. 수정 시 이전 본문 이력을 별도 보관하지 않으며, 작업 이력에는 작업자·시각·버전·게시 여부만 남깁니다. 숨김은 삭제가 아닙니다.
## 설문 참여 방식 및 QR

설문 생성/초안 수정에 access_mode(login 또는 anonymous)를 지정합니다. 기본값은 login이며 게시 후 변경할 수 없습니다.
`GET /api/surveys/{survey_id}/qr.svg`는 survey:manage 권한으로 게시된 설문의 참여 QR SVG를 반환합니다.
`GET /api/public-surveys/{token}`은 공개 예외 경로이며 게시·종료된 익명형만 조회합니다. 초안·휴지통·잘못된 주소는 404입니다. 브라우저용 서명 쿠키와 설문별 CSRF 토큰을 제공합니다.
`POST /api/public-surveys/{token}/responses`는 해당 쿠키와 X-Survey-CSRF 헤더를 요구합니다. 응답 기간·입력 검증·같은 브라우저 중복 방지·요청 제한을 적용합니다. 로그인 계정은 읽지 않으며 결과 조회 권한을 부여하지 않습니다.
로그인형의 기존 응답 API는 익명형 제출을 받지 않습니다. 공개 API는 로그인형 설문을 노출하지 않습니다.
