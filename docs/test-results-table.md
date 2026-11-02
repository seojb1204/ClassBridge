# 자동 테스트 결과표 (자동 생성)

요약: e2e 통과 8, integration 통과 67, postgres 통과 9, unit 통과 29

| 계층 | 테스트 | 검증 요구사항 | 결과 | 시간(s) |
|---|---|---|---|---|
| e2e | `test_student_booking_flow_pc` | §3.1 학생 예약 흐름 PC (브라우저) | 통과 | 4.38 |
| e2e | `test_double_click_creates_single_booking` | §3.4 중복 클릭 (브라우저) | 통과 | 0.68 |
| e2e | `test_professor_completes_consultation` | §3.4 상담 완료 (브라우저) | 통과 | 1.56 |
| e2e | `test_admin_uses_professor_features_and_changes_role` | §2.1 관리자 교수자 기능·권한 변경 (브라우저) | 통과 | 1.39 |
| e2e | `test_survey_create_submit_results` | §4 설문 생성→제출→통계 (브라우저) | 통과 | 2.40 |
| e2e | `test_suggestion_flow` | §5 건의 제출→열람 (브라우저) | 통과 | 1.37 |
| e2e | `test_mobile_student_flow` | §3.1 학생 예약·조회·취소 | 통과 | 1.39 |
| e2e | `test_mobile_professor_views` | §3.1 모바일 교수자 화면 (브라우저) | 통과 | 1.01 |
| integration | `test_every_api_route_declares_permission` | §2.3 기본 거부: 모든 API 권한 선언 | 통과 | 0.04 |
| integration | `test_unauthenticated_is_rejected` | §2.3 미로그인 거부 | 통과 | 0.10 |
| integration | `test_student_cannot_call_professor_apis` | §2.3 학생→교수자 API 거부 | 통과 | 0.26 |
| integration | `test_student_cannot_call_admin_apis` | §2.3 학생→관리자 API 거부 | 통과 | 0.21 |
| integration | `test_professor_cannot_use_admin_only` | §2.3 교수자→관리자 설정 거부 | 통과 | 0.18 |
| integration | `test_admin_can_use_all_professor_features` | §2.3 관리자의 교수자 기능 허용 | 통과 | 0.35 |
| integration | `test_cannot_access_other_students_booking` | §2.3 타인 예약 조회·수정·취소 거부 | 통과 | 0.28 |
| integration | `test_student_booking_view_hides_notes` | §7.2 상담 기록 열람 권한 | 통과 | 0.26 |
| integration | `test_revoked_admin_session_is_rejected` | §2.3 권한 회수 후 기존 세션 거부 | 통과 | 0.28 |
| integration | `test_client_side_role_tampering_has_no_effect` | §2.3 브라우저 역할 조작 무효 | 통과 | 0.18 |
| integration | `test_csrf_required_for_mutations` | §7.2 CSRF 방어 | 통과 | 0.22 |
| integration | `test_security_headers` | §7.2 보안 헤더 | 통과 | 0.18 |
| integration | `test_session_cookie_flags` | §7.2 안전한 쿠키 | 통과 | 0.08 |
| integration | `test_bootstrap_roles_from_env_allowlist` | §2.2 초기 관리자·교수 등록 | 통과 | 0.17 |
| integration | `test_admin_cannot_change_own_role` | §2.2 자기 권한 변경 차단 | 통과 | 0.15 |
| integration | `test_last_admin_cannot_be_demoted_or_deactivated` | §2.2 유일한 관리자 보호 | 통과 | 0.25 |
| integration | `test_last_admin_guard_in_service` | §2.2 유일한 관리자 보호 | 통과 | 0.17 |
| integration | `test_deactivation_kills_sessions_and_blocks_login` | §2.2 계정 비활성화·세션 무효화 | 통과 | 0.26 |
| integration | `test_role_change_is_audited` | §2.2 권한 변경 기록 | 통과 | 0.21 |
| integration | `test_env_allowlist_does_not_promote_existing_user_when_admin_exists` | §2.2 최초 관리자 부여 절차 보호 | 통과 | 0.14 |
| integration | `test_env_allowlist_recovers_when_no_admin` | §2.2 최초 관리자 부여 절차 보호 | 통과 | 0.09 |
| integration | `test_settings_update_and_validation` | §3.3 관리자 설정 변경 | 통과 | 0.21 |
| integration | `test_domain_restriction` | §2.2 허용 도메인 | 통과 | 0.07 |
| integration | `test_student_flow_book_view_cancel` | §3.1 학생 예약·조회·취소 | 통과 | 0.30 |
| integration | `test_one_active_booking_per_student` | §3.3 1인 1활성 예약 | 통과 | 0.23 |
| integration | `test_duplicate_click_same_slot` | §3.4 중복 클릭 | 통과 | 0.27 |
| integration | `test_individual_slot_capacity_and_group_remaining` | §3.3 개인·단체 정원, 남은 자리 | 통과 | 0.28 |
| integration | `test_individual_requires_capacity_one` | §3.2 개인 상담 정원 | 통과 | 0.22 |
| integration | `test_cancel_deadline_three_hours` | §3.3 취소 3시간 전 제한 | 통과 | 0.26 |
| integration | `test_booking_deadline_and_window` | §3.3 예약 마감·예약 가능 범위 | 통과 | 0.25 |
| integration | `test_reschedule_success_and_atomic_failure` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.27 |
| integration | `test_cancel_then_other_student_books` | §3.4 취소 직후 다른 학생 예약 | 통과 | 0.25 |
| integration | `test_capacity_cannot_drop_below_booked` | §3.4 정원 축소 시 초과 방지 | 통과 | 0.24 |
| integration | `test_delete_slot_with_bookings_requires_force` | §3.4 예약된 시간대 삭제 | 통과 | 0.36 |
| integration | `test_slot_overlap_rejected` | §3.4 시간표 충돌 | 통과 | 0.22 |
| integration | `test_break_and_repeat_generation` | §3.2 휴식·반복 일정 | 통과 | 0.22 |
| integration | `test_blackout_blocks_slot_generation` | §3.4 휴무일 | 통과 | 0.25 |
| integration | `test_outcome_requires_slot_started` | §3.4 상담 완료·미참석 | 통과 | 0.31 |
| integration | `test_staff_books_on_behalf_and_audit` | §2.1 교수자 대리 예약·감사 | 통과 | 0.23 |
| integration | `test_professor_cannot_self_book` | §2.1 교수자 본인 예약 불가 | 통과 | 0.22 |
| integration | `test_db_unavailable_returns_503` | §3.4 DB 장애 응답 | 통과 | 0.19 |
| integration | `test_google_login_flow` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.10 |
| integration | `test_state_mismatch_rejected` | §7.2 OAuth state 검증 | 통과 | 0.09 |
| integration | `test_unverified_email_rejected` | §2.2 인증되지 않은 이메일 거부 | 통과 | 0.07 |
| integration | `test_identity_bound_to_sub_not_email` | §2.2 계정 ID 기준 식별 | 통과 | 0.10 |
| integration | `test_verifier_failure_is_401` | §7.2 ID 토큰 검증 실패 | 통과 | 0.07 |
| integration | `test_sqlite_upgrade_matches_models_and_downgrade` | §7.1 마이그레이션 (SQLite) | 통과 | 0.20 |
| integration | `test_submit_and_read` | §5 건의 제출·열람 | 통과 | 0.25 |
| integration | `test_no_author_stored` | §5 건의 작성자 미저장 | 통과 | 0.25 |
| integration | `test_rate_limit_blocks_bursts_not_total` | §5 남용 방지 (횟수 무제한·속도 제한) | 통과 | 0.29 |
| integration | `test_content_validation` | §5 악성·과대 입력 | 통과 | 0.25 |
| integration | `test_html_stored_as_text` | §7.2 XSS 방어 | 통과 | 0.20 |
| integration | `test_local_analysis` | §10 반복 의견 분석 | 통과 | 0.28 |
| integration | `test_consultation_notes_never_reach_analysis` | §10 상담 기록 외부 AI 미전송·PII 마스킹 | 통과 | 0.28 |
| integration | `test_external_ai_hallucinated_refs_dropped_and_failure_fallback` | §10 근거 없는 AI 결과 제거·장애 시 기본 기능 유지 | 통과 | 0.24 |
| integration | `test_ai_disabled` | §10 AI 비활성화 | 통과 | 0.20 |
| integration | `test_full_survey_flow` | §4 설문 제출·통계 | 통과 | 0.32 |
| integration | `test_duplicate_submission_blocked` | §4.2 중복 참여 방지 | 통과 | 0.25 |
| integration | `test_answer_validation` | §8 설문 입력값 검증 | 통과 | 0.24 |
| integration | `test_questions_locked_after_publish_and_duplicate` | §4.1 게시 후 문항 수정 정책 | 통과 | 0.28 |
| integration | `test_draft_not_visible_and_closed_not_submittable` | §4.1 게시·종료 상태 | 통과 | 0.29 |
| integration | `test_question_validation` | §8 설문 입력값 검증 | 통과 | 0.24 |
| integration | `test_export_xlsx_sanitizes_formulas` | §7.2 엑셀 수식 주입 방어 | 통과 | 0.34 |
| integration | `test_anonymity_schema_has_no_link` | §4.2 익명 응답 분리 | 통과 | 0.06 |
| integration | `test_staff_cannot_see_who_participated` | §4.2 개인별 참여 여부 비공개 | 통과 | 0.29 |
| integration | `test_no_submission_audit_or_log` | §4.2 로그·감사기록에 익명 제출 미기록 | 통과 | 0.27 |
| integration | `test_feature_flag_disables_surveys` | §4.2 검토 전 비활성화 스위치 | 통과 | 0.14 |
| postgres | `test_migration_matches_models_and_downgrades` | §7.1 마이그레이션 | 통과 | 0.71 |
| postgres | `test_concurrent_last_seat_individual` | §3.4 동시 마지막 자리 (PostgreSQL) | 통과 | 0.58 |
| postgres | `test_concurrent_group_capacity` | §3.4 단체 정원 동시성 (PostgreSQL) | 통과 | 0.83 |
| postgres | `test_same_student_double_booking_race` | §3.3 1인 1예약 동시성 (PostgreSQL) | 통과 | 0.31 |
| postgres | `test_reschedule_vs_booking_race` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.32 |
| postgres | `test_concurrent_survey_double_submit` | §4.2 동시 중복 제출 (PostgreSQL) | 통과 | 0.33 |
| postgres | `test_concurrent_cross_demotion_keeps_an_admin` | §2.2 동시 상호 강등 (PostgreSQL) | 통과 | 0.25 |
| postgres | `test_capacity_check_constraint_enforced_by_db` | §3.3 DB CHECK 제약 (PostgreSQL) | 통과 | 0.23 |
| postgres | `test_service_conflict_type` | 내부 일관성 | 통과 | 0.12 |
| unit | `test_admin_is_superset_of_professor` | §2.1 Admin ⊇ Professor | 통과 | 0.00 |
| unit | `test_student_has_no_staff_permissions` | §2.1 권한표 | 통과 | 0.00 |
| unit | `test_professor_lacks_admin_only` | §2.1 권한표 | 통과 | 0.00 |
| unit | `test_unknown_role_denied` | §2.2 자기 권한 변경 차단 | 통과 | 0.00 |
| unit | `test_no_deanonymization_permission_exists` | §2.1 권한표 | 통과 | 0.00 |
| unit | `test_generate_blocks_with_break` | §3.2 시간 블록 생성 | 통과 | 0.00 |
| unit | `test_generate_blocks_kst_to_utc` | §3.2 시간 블록 생성 | 통과 | 0.00 |
| unit | `test_generate_blocks_invalid[3-0-start0-end0]` | §3.2 시간 블록 생성 | 통과 | 0.00 |
| unit | `test_generate_blocks_invalid[30--1-start1-end1]` | §3.2 시간 블록 생성 | 통과 | 0.00 |
| unit | `test_generate_blocks_invalid[30-0-start2-end2]` | §3.2 시간 블록 생성 | 통과 | 0.00 |
| unit | `test_generate_blocks_invalid[90-0-start3-end3]` | §3.2 시간 블록 생성 | 통과 | 0.00 |
| unit | `test_expand_days_weekly` | §3.2 반복 요일 | 통과 | 0.00 |
| unit | `test_booking_deadline_boundaries` | §3.3 예약 마감·예약 가능 범위 | 통과 | 0.00 |
| unit | `test_cancel_deadline_boundaries` | §3.3 취소 3시간 전 제한 | 통과 | 0.00 |
| unit | `test_transitions` | §8 예약 상태 전환 | 통과 | 0.00 |
| unit | `test_validate_answers` | §8 설문 입력값 | 통과 | 0.00 |
| unit | `test_validate_questions_strips_options_for_text` | §8 문항 검증 | 통과 | 0.00 |
| unit | `test_excel_sanitize[=1+1]` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_excel_sanitize[+cmd]` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_excel_sanitize[-2+3]` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_excel_sanitize[@SUM(A1)]` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_excel_sanitize[\t=x]` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_excel_sanitize[ =x]` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_excel_sanitize_keeps_normal` | §7.2 엑셀 수식 주입 | 통과 | 0.00 |
| unit | `test_scrub_pii` | §10 개인정보 마스킹 | 통과 | 0.00 |
| unit | `test_rate_limiter_window` | §5 남용 방지 (횟수 무제한·속도 제한) | 통과 | 0.00 |
| unit | `test_access_log_filter_hides_anonymous_posts` | §4.2 익명 제출 접근 로그 차단 | 통과 | 0.00 |
| unit | `test_production_config_rejects_unsafe` | §9 운영 설정 안전장치 | 통과 | 0.00 |
| unit | `test_production_config_ok` | §9 운영 설정 안전장치 | 통과 | 0.00 |
