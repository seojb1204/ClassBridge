# API 명세

> `scripts/gen_api_doc.py`로 코드에서 자동 생성. 상세 스키마는 `docs/openapi.json` 또는 개발 서버 `/docs`.

모든 변경 요청(POST/PUT/PATCH/DELETE)에는 `X-CSRF-Token` 헤더가 필요합니다 (`GET /api/me`의 `csrf_token`).
오류 응답 형식: `{"error": "코드", "message": "설명"}`

| 메서드 | 경로 | 필요 권한 | 설명 |
|---|---|---|---|
| GET | `/` | - | 웹 화면 |
| GET | `/api/admin/audit` | audit:view | 관리 작업 이력 조회 |
| PUT | `/api/admin/email-delivery` | settings:manage | email_delivery |
| GET | `/api/admin/notification-summary` | booking:manage | notification_summary |
| GET | `/api/admin/notifications` | settings:manage | notifications |
| POST | `/api/admin/notifications/{notification_id}/resolve` | settings:manage | resolve_notification |
| GET | `/api/admin/personal-alerts` | booking:manage | read_preferences |
| PUT | `/api/admin/personal-alerts` | booking:manage | save_preferences |
| GET | `/api/admin/push-config` | booking:manage | push_config |
| POST | `/api/admin/push-device-remove` | booking:manage | remove_device |
| POST | `/api/admin/push-device-state` | booking:manage | device_state |
| DELETE | `/api/admin/push-subscription` | booking:manage | unsubscribe |
| POST | `/api/admin/push-subscription` | booking:manage | subscribe |
| POST | `/api/admin/push-test` | booking:manage | test_device |
| GET | `/api/admin/settings` | settings:manage | 운영 설정 조회 |
| PUT | `/api/admin/settings` | settings:manage | 운영 설정 변경 |
| GET | `/api/admin/staff-reminders` | settings:manage | listing |
| POST | `/api/admin/staff-reminders` | settings:manage | 설문 생성 (초안) |
| PUT | `/api/admin/staff-reminders/{identifier}/cancel` | settings:manage | cancel |
| GET | `/api/admin/users` | user:manage | 사용자 목록 |
| DELETE | `/api/admin/users/{user_id}` | user:manage | delete_user |
| PUT | `/api/admin/users/{user_id}/active` | user:manage | 계정 활성/비활성 |
| GET | `/api/admin/users/{user_id}/deletion-preview` | user:manage | deletion_preview |
| PUT | `/api/admin/users/{user_id}/role` | role:manage | 역할 변경 (자기 자신·마지막 관리자 불가) |
| POST | `/api/analysis` | ai:analyze | 의견 분석 (로컬/외부 AI) |
| GET | `/api/announcement` | slot:view | get_announcement |
| PUT | `/api/announcement` | announcement:manage | put_announcement |
| GET | `/api/auth/config` | 공개 | 로그인 화면용 공개 정보 (비밀 없음). |
| GET | `/api/booking-policy` | slot:view | booking_policy |
| GET | `/api/bookings` | booking:manage | 예약 현황 조회 |
| POST | `/api/bookings` | slot:view | 예약 생성 (student_id는 교수자·관리자만) |
| GET | `/api/bookings/mine` | booking:self | 내 예약 목록 (상담 기록 제외) |
| POST | `/api/bookings/{booking_id}/cancel` | slot:view | 예약 취소 (학생: 3시간 전까지, 교수자: 사유 필수) |
| GET | `/api/bookings/{booking_id}/history` | booking:manage | 예약 변경 이력 |
| PUT | `/api/bookings/{booking_id}/note` | booking:note | 상담 기록 저장 |
| POST | `/api/bookings/{booking_id}/outcome` | booking:manage | 완료/미참석 처리 |
| POST | `/api/bookings/{booking_id}/reschedule` | slot:view | 예약 변경 (원자적, 실패 시 기존 예약 유지) |
| GET | `/api/bookings/{booking_id}/updates` | booking:self | student_updates |
| POST | `/api/bookings/{booking_id}/updates/{event_id}/read` | booking:self | read_student_update |
| GET | `/api/exports/consultations` | data:export | export_consultations |
| GET | `/api/inbox` | booking:manage | listing |
| PUT | `/api/inbox/read-all` | booking:manage | read_all |
| PUT | `/api/inbox/{notification_id}/read` | booking:manage | read |
| GET | `/api/inbox/{notification_id}/target` | booking:manage | Resolve only an owned, arrived notification. No schema migration or inferred IDs. |
| GET | `/api/lectures` | slot:manage | listing |
| POST | `/api/lectures` | slot:manage | 설문 생성 (초안) |
| GET | `/api/lectures/calendar` | login | Authenticated read-only timetable; no series or author metadata. |
| PATCH | `/api/lectures/{identifier}` | slot:manage | 설문 수정 (게시 후 문항 잠금) |
| POST | `/api/lectures/{identifier}/cancel` | slot:manage | cancel |
| GET | `/api/me` | login | 현재 사용자·권한·CSRF 토큰 |
| GET | `/api/public-surveys/{token}` | 공개 | read |
| POST | `/api/public-surveys/{token}/responses` | 공개 | 익명 제출 |
| GET | `/api/site/qr.png` | 공개 | site_qr_png |
| GET | `/api/site/qr.svg` | 공개 | site_qr |
| GET | `/api/slots` | slot:view | 상담 시간표 조회 |
| POST | `/api/slots` | slot:manage | 상담 시간 일괄 생성 (반복·휴식·휴무일 제외) |
| GET | `/api/slots/available-days` | slot:view | available_days |
| POST | `/api/slots/preview` | slot:manage | preview_slots |
| POST | `/api/slots/replace` | slot:manage | replace_unbooked_slots |
| DELETE | `/api/slots/{slot_id}` | slot:manage | delete_empty_slot |
| PATCH | `/api/slots/{slot_id}` | slot:manage | 상담 시간 수정 (정원 축소 제한) |
| POST | `/api/slots/{slot_id}/cancel` | slot:manage | 상담 시간 취소 (예약 있으면 force+사유) |
| GET | `/api/staff/booking-events` | booking:manage | booking_events |
| GET | `/api/staff/notes` | booking:note | staff_notes |
| GET | `/api/staff/overview` | booking:manage | staff_overview |
| GET | `/api/students` | booking:manage | 대리 예약용 학생 목록 |
| GET | `/api/suggestions` | suggestion:read | 건의 목록 |
| POST | `/api/suggestions` | suggestion:submit | 익명 제출 |
| POST | `/api/suggestions/anonymous` | 공개 | submit_anonymous |
| GET | `/api/suggestions/public` | slot:view | public_board |
| POST | `/api/suggestions/receipt` | 공개 | receipt |
| POST | `/api/suggestions/search` | suggestion:read | search_content |
| GET | `/api/suggestions/stats` | suggestion:read | 건의 통계 |
| POST | `/api/suggestions/trash/delete-selected` | suggestion:read | delete_selected_trash |
| POST | `/api/suggestions/trash/empty` | suggestion:read | empty_trash |
| GET | `/api/suggestions/trash/preview` | suggestion:read | preview_trash |
| POST | `/api/suggestions/{sid}/purge` | suggestion:read | purge_suggestion |
| POST | `/api/suggestions/{sid}/replies` | suggestion:read | add_reply |
| POST | `/api/suggestions/{sid}/restore` | suggestion:read | restore_suggestion |
| POST | `/api/suggestions/{sid}/trash` | suggestion:read | trash_suggestion |
| PUT | `/api/suggestions/{suggestion_id}/status` | suggestion:read | 건의 상태 변경 |
| GET | `/api/support/counts` | slot:view | counts |
| GET | `/api/support/tickets` | slot:view | tickets |
| POST | `/api/support/tickets` | slot:view | 설문 생성 (초안) |
| GET | `/api/support/tickets/{tid}` | slot:view | detail |
| POST | `/api/support/tickets/{tid}/messages` | slot:view | respond |
| POST | `/api/support/tickets/{tid}/read` | slot:view | mark_read |
| PUT | `/api/support/tickets/{tid}/status` | support:manage | status |
| GET | `/api/surveys` | survey:manage | 설문 목록 (응답 수 포함) |
| POST | `/api/surveys` | survey:manage | 설문 생성 (초안) |
| GET | `/api/surveys/student/list` | survey:respond | 학생용 설문 목록 (본인 참여 여부) |
| GET | `/api/surveys/student/{survey_id}` | survey:respond | 학생용 설문 상세 |
| POST | `/api/surveys/{sid}/purge` | survey:manage | purge_survey |
| POST | `/api/surveys/{sid}/restore` | survey:manage | restore_survey |
| POST | `/api/surveys/{sid}/trash` | survey:manage | trash_survey |
| DELETE | `/api/surveys/{survey_id}` | survey:manage | 초안 삭제 |
| GET | `/api/surveys/{survey_id}` | survey:manage | 설문 상세 |
| PATCH | `/api/surveys/{survey_id}` | survey:manage | 설문 수정 (게시 후 문항 잠금) |
| POST | `/api/surveys/{survey_id}/close` | survey:manage | 설문 종료 |
| POST | `/api/surveys/{survey_id}/duplicate` | survey:manage | 설문 복제 (새 버전) |
| GET | `/api/surveys/{survey_id}/export.xlsx` | data:export | 엑셀 다운로드 (수식 주입 방어) |
| POST | `/api/surveys/{survey_id}/publish` | survey:manage | 설문 게시 |
| GET | `/api/surveys/{survey_id}/qr.png` | survey:manage | survey_qr_png |
| GET | `/api/surveys/{survey_id}/qr.svg` | survey:manage | survey_qr |
| POST | `/api/surveys/{survey_id}/responses` | survey:respond | 익명 제출 |
| GET | `/api/surveys/{survey_id}/results` | survey:results | 설문 결과 (최소 응답 수 미만이면 숨김) |
| POST | `/auth/dev/login` | - | 개발용 로그인 (운영 불가) |
| GET | `/auth/google/callback` | - | Google 로그인 콜백 |
| GET | `/auth/google/login` | - | Google 로그인 시작 |
| POST | `/auth/logout` | login | 로그아웃 |
| GET | `/healthz` | - | 상태 확인 |
| GET | `/privacy` | - | privacy_notice |
| GET | `/readyz` | - | readyz |
| GET | `/sw.js` | - | service_worker |
