# 자동 테스트 결과표 (자동 생성)

요약: e2e 통과 175, integration 통과 312, postgres 건너뜀 39, test_editorial_palette 통과 15, test_lecture_review 통과 6, test_lectures 통과 6, test_student_lecture_calendar 통과 1, test_weekday_policy 통과 8, unit 통과 61

| 계층 | 테스트 | 검증 요구사항 | 결과 | 시간(s) |
|---|---|---|---|---|
| e2e | `test_booking_back_close_reopen_and_explicit_close[viewport0]` | — | 통과 | 3.90 |
| e2e | `test_booking_back_close_reopen_and_explicit_close[viewport1]` | — | 통과 | 1.25 |
| e2e | `test_back_during_submit_and_failed_submit` | — | 통과 | 1.02 |
| e2e | `test_mobile_booking_week_navigation_keeps_scroll` | — | 통과 | 6.17 |
| e2e | `test_delegate_booking_moved_to_registration` | — | 통과 | 0.93 |
| e2e | `test_booking_swipe_uses_connected_280ms_slide[False]` | — | 통과 | 2.07 |
| e2e | `test_booking_swipe_uses_connected_280ms_slide[True]` | — | 통과 | 2.25 |
| e2e | `test_shared_editor_preserves_notes_and_allows_outcome_correction[390]` | §3.4 상담 완료·미참석 | 통과 | 3.17 |
| e2e | `test_shared_editor_preserves_notes_and_allows_outcome_correction[1280]` | §3.4 상담 완료·미참석 | 통과 | 0.50 |
| e2e | `test_history_period_is_independent_of_status` | — | 통과 | 1.10 |
| e2e | `test_minimum_axis_and_outside_events[1280]` | — | 통과 | 2.96 |
| e2e | `test_minimum_axis_and_outside_events[390]` | — | 통과 | 0.58 |
| e2e | `test_available_and_reserved_are_distinct[1280-week]` | — | 통과 | 3.02 |
| e2e | `test_available_and_reserved_are_distinct[360-week]` | — | 통과 | 0.41 |
| e2e | `test_available_and_reserved_are_distinct[390-week]` | — | 통과 | 0.39 |
| e2e | `test_available_and_reserved_are_distinct[390-list]` | — | 통과 | 0.56 |
| e2e | `test_empty_time_prefills_both_registration_kinds[prof@test.ac.kr]` | — | 통과 | 3.54 |
| e2e | `test_empty_time_prefills_both_registration_kinds[admin@test.ac.kr]` | — | 통과 | 0.77 |
| e2e | `test_student_blank_time_does_not_create_booking` | — | 통과 | 0.87 |
| e2e | `test_calendar_default_and_compact_controls[360]` | — | 통과 | 4.14 |
| e2e | `test_calendar_default_and_compact_controls[390]` | — | 통과 | 1.42 |
| e2e | `test_calendar_default_and_compact_controls[1280]` | — | 통과 | 1.41 |
| e2e | `test_compact_support_panels[compact-student@test.ac.kr-/booking-360]` | — | 통과 | 3.89 |
| e2e | `test_compact_support_panels[compact-student@test.ac.kr-/booking-390]` | — | 통과 | 1.26 |
| e2e | `test_compact_support_panels[compact-student@test.ac.kr-/booking-1366]` | — | 통과 | 1.33 |
| e2e | `test_compact_support_panels[prof@test.ac.kr-/slots-360]` | — | 통과 | 1.45 |
| e2e | `test_compact_support_panels[prof@test.ac.kr-/slots-390]` | — | 통과 | 1.34 |
| e2e | `test_compact_support_panels[prof@test.ac.kr-/slots-1366]` | — | 통과 | 1.51 |
| e2e | `test_staff_menu_calendar_and_activity_rows[1280]` | — | 통과 | 3.79 |
| e2e | `test_staff_menu_calendar_and_activity_rows[933]` | — | 통과 | 1.23 |
| e2e | `test_staff_menu_calendar_and_activity_rows[390]` | — | 통과 | 1.31 |
| e2e | `test_role_navigation_and_disabled_features[prof@test.ac.kr-True]` | — | 통과 | 1.23 |
| e2e | `test_role_navigation_and_disabled_features[compact-student@test.ac.kr-False]` | — | 통과 | 1.08 |
| e2e | `test_activity_retry_keeps_latest_first_and_pagination` | — | 통과 | 1.15 |
| e2e | `test_consultation_hides_only_overlapping_lecture_time[False-1280]` | §3.4 시간표 충돌 | 통과 | 3.04 |
| e2e | `test_consultation_hides_only_overlapping_lecture_time[False-390]` | §3.4 시간표 충돌 | 통과 | 0.49 |
| e2e | `test_consultation_hides_only_overlapping_lecture_time[True-1280]` | §3.4 시간표 충돌 | 통과 | 0.37 |
| e2e | `test_consultation_hides_only_overlapping_lecture_time[True-390]` | §3.4 시간표 충돌 | 통과 | 0.72 |
| e2e | `test_staff_booking_activity_mobile_filter_pagination_and_student_access` | — | 통과 | 5.34 |
| e2e | `test_live_booking_refresh_preserves_dialog_and_stops_after_navigation` | — | 통과 | 1.25 |
| e2e | `test_staff_today_and_actionable_notification_error` | — | 통과 | 1.30 |
| e2e | `test_mobile_day_selection_scroll_notice_order_and_student_no_export` | — | 통과 | 2.69 |
| e2e | `test_editor_direct_trash_and_empty_account_cleanup` | — | 통과 | 3.18 |
| e2e | `test_booking_announcement_mobile_lifecycle` | — | 통과 | 6.08 |
| e2e | `test_anonymous_survey_qr_and_direct_response` | — | 통과 | 7.00 |
| e2e | `test_pwa_install_guide_all_bookings_and_private_offline` | — | 통과 | 2.50 |
| e2e | `test_pwa_standalone_staff_home` | — | 통과 | 0.93 |
| e2e | `test_student_booking_flow_pc` | §3.1 학생 예약 흐름 PC (브라우저) | 통과 | 4.18 |
| e2e | `test_week_calendar_time_scale_is_stable_across_durations` | — | 통과 | 1.58 |
| e2e | `test_double_click_creates_single_booking` | §3.4 중복 클릭 (브라우저) | 통과 | 0.85 |
| e2e | `test_professor_completes_consultation` | §3.4 상담 완료 (브라우저) | 통과 | 1.84 |
| e2e | `test_admin_uses_professor_features_and_changes_role` | §2.1 관리자 교수자 기능·권한 변경 (브라우저) | 통과 | 2.25 |
| e2e | `test_survey_create_submit_results` | §4 설문 생성→제출→통계 (브라우저) | 통과 | 2.72 |
| e2e | `test_suggestion_flow` | §5 건의 제출→열람 (브라우저) | 통과 | 2.32 |
| e2e | `test_mobile_student_flow` | §3.1 학생 예약·조회·취소 | 통과 | 2.68 |
| e2e | `test_mobile_staff_insights_and_timetable` | — | 통과 | 1.62 |
| e2e | `test_mobile_professor_views` | §3.1 모바일 교수자 화면 (브라우저) | 통과 | 0.95 |
| e2e | `test_mobile_optional_sections_do_not_render_null` | — | 통과 | 1.48 |
| e2e | `test_public_suggestion_reply_trash_and_restore` | — | 통과 | 3.30 |
| e2e | `test_survey_trash_restore_and_purge_ui` | — | 통과 | 1.79 |
| e2e | `test_consultation_download_and_print_view` | — | 통과 | 1.18 |
| e2e | `test_developer_support_private_conversation_and_menu` | — | 통과 | 5.41 |
| e2e | `test_mobile_available_slot_counts_in_staff_views` | — | 통과 | 1.80 |
| e2e | `test_site_qr_available_to_guests_students_and_staff` | — | 통과 | 3.23 |
| e2e | `test_daytime_input_parser_boundaries` | — | 통과 | 0.76 |
| e2e | `test_simple_weekly_schedule_preview_summary_and_delete` | — | 통과 | 5.18 |
| e2e | `test_late_calendar_response_does_not_overwrite_new_page` | — | 통과 | 0.76 |
| e2e | `test_preview_month_boundary_and_professor_notification_summary[mobile]` | — | 통과 | 1.09 |
| e2e | `test_preview_month_boundary_and_professor_notification_summary[pc]` | — | 통과 | 0.97 |
| e2e | `test_staff_personal_alerts_mobile` | — | 통과 | 1.30 |
| e2e | `test_guest_opens_writer_from_login` | — | 통과 | 0.52 |
| e2e | `test_mobile_booking_summary` | — | 통과 | 0.97 |
| e2e | `test_unresolved_history_filter_includes_past_and_allows_staff_correction[viewport0]` | — | 통과 | 0.88 |
| e2e | `test_unresolved_history_filter_includes_past_and_allows_staff_correction[viewport1]` | — | 통과 | 0.96 |
| e2e | `test_flexible_sentence_populates_form_without_registering` | — | 통과 | 0.87 |
| e2e | `test_weekday_calendar_preserves_legacy_weekend_access[viewport0]` | — | 통과 | 0.47 |
| e2e | `test_weekday_calendar_preserves_legacy_weekend_access[viewport1]` | — | 통과 | 0.76 |
| e2e | `test_editorial_all_roles_layout[prof@test.ac.kr-routes0-viewport0]` | — | 통과 | 3.77 |
| e2e | `test_editorial_all_roles_layout[prof@test.ac.kr-routes0-viewport1]` | — | 통과 | 1.03 |
| e2e | `test_editorial_all_roles_layout[prof@test.ac.kr-routes0-viewport2]` | — | 통과 | 1.09 |
| e2e | `test_editorial_all_roles_layout[admin@test.ac.kr-routes1-viewport0]` | — | 통과 | 1.11 |
| e2e | `test_editorial_all_roles_layout[admin@test.ac.kr-routes1-viewport1]` | — | 통과 | 1.05 |
| e2e | `test_editorial_all_roles_layout[admin@test.ac.kr-routes1-viewport2]` | — | 통과 | 1.05 |
| e2e | `test_editorial_all_roles_layout[design-student@test.ac.kr-routes2-viewport0]` | — | 통과 | 0.92 |
| e2e | `test_editorial_all_roles_layout[design-student@test.ac.kr-routes2-viewport1]` | — | 통과 | 0.84 |
| e2e | `test_editorial_all_roles_layout[design-student@test.ac.kr-routes2-viewport2]` | — | 통과 | 1.09 |
| e2e | `test_oauth_return_with_active_worker_exchanges_code_once[viewport0]` | — | 통과 | 2.65 |
| e2e | `test_oauth_return_with_active_worker_exchanges_code_once[viewport1]` | — | 통과 | 2.05 |
| e2e | `test_staff_manual_lecture_same_calendar[viewport0]` | — | 통과 | 4.29 |
| e2e | `test_staff_manual_lecture_same_calendar[viewport1]` | — | 통과 | 1.41 |
| e2e | `test_lecture_discoverable_before_notice[viewport0-prof@test.ac.kr]` | — | 통과 | 0.86 |
| e2e | `test_lecture_discoverable_before_notice[viewport0-admin@test.ac.kr]` | — | 통과 | 0.89 |
| e2e | `test_lecture_discoverable_before_notice[viewport1-prof@test.ac.kr]` | — | 통과 | 0.88 |
| e2e | `test_lecture_discoverable_before_notice[viewport1-admin@test.ac.kr]` | — | 통과 | 0.83 |
| e2e | `test_mobile_calendar_week_list_and_details[viewport0-prof@test.ac.kr-/slots]` | — | 통과 | 1.89 |
| e2e | `test_mobile_calendar_week_list_and_details[viewport0-admin@test.ac.kr-/slots]` | — | 통과 | 1.84 |
| e2e | `test_mobile_calendar_week_list_and_details[viewport0-grid-student@test.ac.kr-/booking]` | — | 통과 | 2.22 |
| e2e | `test_mobile_calendar_week_list_and_details[viewport1-prof@test.ac.kr-/slots]` | — | 통과 | 1.73 |
| e2e | `test_mobile_calendar_week_list_and_details[viewport1-admin@test.ac.kr-/slots]` | — | 통과 | 1.70 |
| e2e | `test_mobile_calendar_week_list_and_details[viewport1-grid-student@test.ac.kr-/booking]` | — | 통과 | 1.86 |
| e2e | `test_mobile_calendar_scroll_chains_at_vertical_edges[390]` | — | 통과 | 5.61 |
| e2e | `test_mobile_calendar_scroll_chains_at_vertical_edges[360]` | — | 통과 | 5.77 |
| e2e | `test_mobile_week_swipe_threshold_and_taps[False-360]` | — | 통과 | 9.20 |
| e2e | `test_mobile_week_swipe_threshold_and_taps[False-390]` | — | 통과 | 9.02 |
| e2e | `test_mobile_week_swipe_threshold_and_taps[True-360]` | — | 통과 | 9.25 |
| e2e | `test_mobile_week_swipe_threshold_and_taps[True-390]` | — | 통과 | 8.99 |
| e2e | `test_mobile_week_swipe_center_and_diagonal_start[360]` | — | 통과 | 5.09 |
| e2e | `test_mobile_week_swipe_center_and_diagonal_start[390]` | — | 통과 | 5.33 |
| e2e | `test_compact_rows_summary_manage_and_back[viewport0]` | — | 통과 | 3.57 |
| e2e | `test_compact_rows_summary_manage_and_back[viewport1]` | — | 통과 | 1.59 |
| e2e | `test_professor_inbox_read_and_refresh[viewport0]` | — | 통과 | 3.75 |
| e2e | `test_professor_inbox_read_and_refresh[viewport1]` | — | 통과 | 0.82 |
| e2e | `test_header_bell_is_accessible_and_preserves_more[viewport0-prof@test.ac.kr]` | — | 통과 | 1.05 |
| e2e | `test_header_bell_is_accessible_and_preserves_more[viewport0-admin@test.ac.kr]` | — | 통과 | 1.12 |
| e2e | `test_header_bell_is_accessible_and_preserves_more[viewport1-prof@test.ac.kr]` | — | 통과 | 1.25 |
| e2e | `test_header_bell_is_accessible_and_preserves_more[viewport1-admin@test.ac.kr]` | — | 통과 | 1.20 |
| e2e | `test_student_has_no_staff_bell_or_inbox_requests[viewport0]` | §2.1 권한표 | 통과 | 0.87 |
| e2e | `test_student_has_no_staff_bell_or_inbox_requests[viewport1]` | §2.1 권한표 | 통과 | 0.94 |
| e2e | `test_inbox_can_reach_older_unread_notifications[viewport0]` | — | 통과 | 0.67 |
| e2e | `test_inbox_can_reach_older_unread_notifications[viewport1]` | — | 통과 | 0.70 |
| e2e | `test_content_open_marks_read_and_read_all_survives_reload[prof@test.ac.kr-viewport0]` | — | 통과 | 1.50 |
| e2e | `test_content_open_marks_read_and_read_all_survives_reload[prof@test.ac.kr-viewport1]` | — | 통과 | 1.51 |
| e2e | `test_content_open_marks_read_and_read_all_survives_reload[admin@test.ac.kr-viewport0]` | — | 통과 | 1.47 |
| e2e | `test_content_open_marks_read_and_read_all_survives_reload[admin@test.ac.kr-viewport1]` | — | 통과 | 1.54 |
| e2e | `test_read_failure_does_not_hide_count_and_focus_refreshes[viewport0]` | — | 통과 | 0.85 |
| e2e | `test_read_failure_does_not_hide_count_and_focus_refreshes[viewport1]` | — | 통과 | 0.75 |
| e2e | `test_close_during_read_does_not_navigate_and_storage_refreshes[viewport0]` | — | 통과 | 1.09 |
| e2e | `test_close_during_read_does_not_navigate_and_storage_refreshes[viewport1]` | — | 통과 | 1.11 |
| e2e | `test_notification_target_exact_cancelled_and_legacy[viewport0]` | — | 통과 | 3.82 |
| e2e | `test_notification_target_exact_cancelled_and_legacy[viewport1]` | — | 통과 | 3.75 |
| e2e | `test_escape_after_inbox_refresh_replaces_focused_control[viewport0]` | — | 통과 | 1.39 |
| e2e | `test_escape_after_inbox_refresh_replaces_focused_control[viewport1]` | — | 통과 | 1.69 |
| e2e | `test_mobile_public_notice_and_direct_login` | — | 통과 | 3.60 |
| e2e | `test_registration_calendar_and_sentence_sync[360]` | — | 통과 | 3.38 |
| e2e | `test_registration_calendar_and_sentence_sync[390]` | — | 통과 | 1.01 |
| e2e | `test_registration_calendar_and_sentence_sync[1280]` | — | 통과 | 1.19 |
| e2e | `test_one_click_same_id_change_beyond_new_booking_horizon[viewport0]` | — | 통과 | 4.68 |
| e2e | `test_one_click_same_id_change_beyond_new_booking_horizon[viewport1]` | — | 통과 | 2.42 |
| e2e | `test_staff_calendar_names_and_cached_navigation[viewport0]` | — | 통과 | 4.38 |
| e2e | `test_staff_calendar_names_and_cached_navigation[viewport1]` | — | 통과 | 1.64 |
| e2e | `test_staff_calendar_names_and_cached_navigation[viewport2]` | — | 통과 | 1.77 |
| e2e | `test_student_real_lectures_and_consultation_priority[viewport0]` | — | 통과 | 3.45 |
| e2e | `test_student_real_lectures_and_consultation_priority[viewport1]` | — | 통과 | 1.02 |
| e2e | `test_error_toast_dismisses_immediately[viewport0]` | — | 통과 | 0.64 |
| e2e | `test_error_toast_dismisses_immediately[viewport1]` | — | 통과 | 0.89 |
| e2e | `test_private_receipt_roundtrip[viewport0]` | — | 통과 | 3.02 |
| e2e | `test_private_receipt_roundtrip[viewport1]` | — | 통과 | 0.38 |
| e2e | `test_student_change_read_ack_and_staff_menu[viewport0]` | — | 통과 | 1.92 |
| e2e | `test_student_change_read_ack_and_staff_menu[viewport1]` | — | 통과 | 2.09 |
| e2e | `test_suggestion_search_sort_and_safe_details[viewport0]` | — | 통과 | 3.53 |
| e2e | `test_suggestion_search_sort_and_safe_details[viewport1]` | — | 통과 | 0.84 |
| e2e | `test_late_suggestion_filter_cannot_replace_latest_results` | — | 통과 | 0.74 |
| e2e | `test_trash_yes_no_and_empty_all_ignore_filters[prof@test.ac.kr-viewport0]` | — | 통과 | 1.14 |
| e2e | `test_trash_yes_no_and_empty_all_ignore_filters[prof@test.ac.kr-viewport1]` | — | 통과 | 1.01 |
| e2e | `test_trash_yes_no_and_empty_all_ignore_filters[admin@test.ac.kr-viewport0]` | — | 통과 | 1.09 |
| e2e | `test_trash_yes_no_and_empty_all_ignore_filters[admin@test.ac.kr-viewport1]` | — | 통과 | 1.08 |
| e2e | `test_trash_select_all_except_one_and_cancel[prof@test.ac.kr-viewport0]` | — | 통과 | 1.05 |
| e2e | `test_trash_select_all_except_one_and_cancel[prof@test.ac.kr-viewport1]` | — | 통과 | 1.11 |
| e2e | `test_trash_select_all_except_one_and_cancel[admin@test.ac.kr-viewport0]` | — | 통과 | 1.11 |
| e2e | `test_trash_select_all_except_one_and_cancel[admin@test.ac.kr-viewport1]` | — | 통과 | 1.36 |
| e2e | `test_guest_writer_keeps_privacy_visible_and_limits_width[viewport0]` | — | 통과 | 3.34 |
| e2e | `test_guest_writer_keeps_privacy_visible_and_limits_width[viewport1]` | — | 통과 | 0.69 |
| e2e | `test_inbox_read_state_and_disclosure[viewport0]` | — | 통과 | 1.11 |
| e2e | `test_inbox_read_state_and_disclosure[viewport1]` | — | 통과 | 0.95 |
| e2e | `test_late_booking_response_cannot_replace_new_inbox[viewport0]` | — | 통과 | 0.86 |
| e2e | `test_late_booking_response_cannot_replace_new_inbox[viewport1]` | — | 통과 | 0.99 |
| e2e | `test_survey_delete_yes_no_escape_navigation_and_retry[prof@test.ac.kr-viewport0]` | — | 통과 | 3.99 |
| e2e | `test_survey_delete_yes_no_escape_navigation_and_retry[prof@test.ac.kr-viewport1]` | — | 통과 | 1.28 |
| e2e | `test_survey_delete_yes_no_escape_navigation_and_retry[admin@test.ac.kr-viewport0]` | — | 통과 | 1.23 |
| e2e | `test_survey_delete_yes_no_escape_navigation_and_retry[admin@test.ac.kr-viewport1]` | — | 통과 | 1.14 |
| e2e | `test_survey_required_summary_labels_optional_clear[viewport0]` | — | 통과 | 1.13 |
| e2e | `test_survey_required_summary_labels_optional_clear[viewport1]` | — | 통과 | 1.12 |
| e2e | `test_survey_latest_tab_wins` | — | 통과 | 0.85 |
| e2e | `test_disabled_email_status_has_no_null_text[viewport0]` | — | 통과 | 0.80 |
| e2e | `test_disabled_email_status_has_no_null_text[viewport1]` | — | 통과 | 0.97 |
| integration | `test_every_api_route_declares_permission` | §2.3 기본 거부: 모든 API 권한 선언 | 통과 | 0.07 |
| integration | `test_unauthenticated_is_rejected` | §2.3 미로그인 거부 | 통과 | 0.14 |
| integration | `test_student_cannot_call_professor_apis` | §2.3 학생→교수자 API 거부 | 통과 | 0.28 |
| integration | `test_student_cannot_call_admin_apis` | §2.3 학생→관리자 API 거부 | 통과 | 0.17 |
| integration | `test_professor_cannot_use_admin_only` | §2.3 교수자→관리자 설정 거부 | 통과 | 0.17 |
| integration | `test_admin_can_use_all_professor_features` | §2.3 관리자의 교수자 기능 허용 | 통과 | 0.34 |
| integration | `test_cannot_access_other_students_booking` | §2.3 타인 예약 조회·수정·취소 거부 | 통과 | 0.38 |
| integration | `test_student_booking_view_hides_notes` | §7.2 상담 기록 열람 권한 | 통과 | 0.26 |
| integration | `test_revoked_admin_session_is_rejected` | §2.3 권한 회수 후 기존 세션 거부 | 통과 | 0.26 |
| integration | `test_client_side_role_tampering_has_no_effect` | §2.3 브라우저 역할 조작 무효 | 통과 | 0.17 |
| integration | `test_csrf_required_for_mutations` | §7.2 CSRF 방어 | 통과 | 0.23 |
| integration | `test_security_headers` | §7.2 보안 헤더 | 통과 | 0.16 |
| integration | `test_session_cookie_flags` | §7.2 안전한 쿠키 | 통과 | 0.08 |
| integration | `test_account_list_orders_recent_logins_then_name` | — | 통과 | 0.17 |
| integration | `test_empty_student_delete_revokes_session_and_allows_signup` | — | 통과 | 0.19 |
| integration | `test_record_added_after_preview_blocks_delete_and_staff_protected` | — | 통과 | 0.27 |
| integration | `test_bootstrap_roles_from_env_allowlist` | §2.2 초기 관리자·교수 등록 | 통과 | 0.14 |
| integration | `test_admin_cannot_change_own_role` | §2.2 자기 권한 변경 차단 | 통과 | 0.14 |
| integration | `test_last_admin_cannot_be_demoted_or_deactivated` | §2.2 유일한 관리자 보호 | 통과 | 0.22 |
| integration | `test_last_admin_guard_in_service` | §2.2 유일한 관리자 보호 | 통과 | 0.17 |
| integration | `test_deactivation_kills_sessions_and_blocks_login` | §2.2 계정 비활성화·세션 무효화 | 통과 | 0.20 |
| integration | `test_role_change_is_audited` | §2.2 권한 변경 기록 | 통과 | 0.16 |
| integration | `test_env_allowlist_does_not_promote_existing_user_when_admin_exists` | §2.2 최초 관리자 부여 절차 보호 | 통과 | 0.12 |
| integration | `test_env_allowlist_recovers_when_no_admin` | §2.2 최초 관리자 부여 절차 보호 | 통과 | 0.11 |
| integration | `test_settings_update_and_validation` | §3.3 관리자 설정 변경 | 통과 | 0.18 |
| integration | `test_domain_restriction` | §2.2 허용 도메인 | 통과 | 0.08 |
| integration | `test_unified_deadline_ignores_stored_cancellation_setting` | — | 통과 | 0.21 |
| integration | `test_unified_deadline_legacy_write_conflict_is_atomic` | — | 통과 | 0.22 |
| integration | `test_unified_deadline_legacy_precedence_and_storage_preserved` | — | 통과 | 0.19 |
| integration | `test_announcement_lifecycle_and_settings_isolation` | — | 통과 | 0.29 |
| integration | `test_announcement_permissions_and_csrf` | §7.2 CSRF 방어 | 통과 | 0.21 |
| integration | `test_announcement_invalid_input[changes0]` | — | 통과 | 0.21 |
| integration | `test_announcement_invalid_input[changes1]` | — | 통과 | 0.30 |
| integration | `test_announcement_invalid_input[changes2]` | — | 통과 | 0.21 |
| integration | `test_announcement_invalid_input[changes3]` | — | 통과 | 0.21 |
| integration | `test_announcement_invalid_input[changes4]` | — | 통과 | 0.23 |
| integration | `test_announcement_invalid_input[changes5]` | — | 통과 | 0.20 |
| integration | `test_announcement_invalid_input[changes6]` | — | 통과 | 0.43 |
| integration | `test_announcement_stale_edit_preserves_newer_value` | — | 통과 | 0.27 |
| integration | `test_announcement_audit_failure_rolls_back` | — | 통과 | 0.20 |
| integration | `test_completion_boundaries_restart_and_manual_correction` | — | 통과 | 0.32 |
| integration | `test_historical_expiry_preserves_history_and_allows_new_booking` | — | 통과 | 0.27 |
| integration | `test_student_cancellation_visible_to_both_staff_roles_only` | — | 통과 | 0.25 |
| integration | `test_change_is_not_cancellation_and_cursor_is_stable` | — | 통과 | 0.27 |
| integration | `test_slot_cancellation_is_included_and_failed_request_has_no_event` | — | 통과 | 0.23 |
| integration | `test_student_flow_book_view_cancel` | §3.1 학생 예약·조회·취소 | 통과 | 0.22 |
| integration | `test_one_active_booking_per_student` | §3.3 1인 1활성 예약 | 통과 | 0.21 |
| integration | `test_duplicate_click_same_slot` | §3.4 중복 클릭 | 통과 | 0.24 |
| integration | `test_individual_slot_capacity_and_group_remaining` | §3.3 개인·단체 정원, 남은 자리 | 통과 | 0.24 |
| integration | `test_individual_requires_capacity_one` | §3.2 개인 상담 정원 | 통과 | 0.19 |
| integration | `test_cancel_deadline_thirty_minutes` | §3.3 취소 3시간 전 제한 | 통과 | 0.22 |
| integration | `test_booking_deadline_and_window` | §3.3 예약 마감·예약 가능 범위 | 통과 | 0.24 |
| integration | `test_half_hour_availability_matches_booking_and_date_filter` | — | 통과 | 0.22 |
| integration | `test_reschedule_success_and_atomic_failure` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.28 |
| integration | `test_cancel_then_other_student_books` | §3.4 취소 직후 다른 학생 예약 | 통과 | 0.23 |
| integration | `test_capacity_cannot_drop_below_booked` | §3.4 정원 축소 시 초과 방지 | 통과 | 0.23 |
| integration | `test_delete_slot_with_bookings_requires_force` | §3.4 예약된 시간대 삭제 | 통과 | 0.30 |
| integration | `test_slot_overlap_rejected` | §3.4 시간표 충돌 | 통과 | 0.46 |
| integration | `test_break_and_repeat_generation` | §3.2 휴식·반복 일정 | 통과 | 0.18 |
| integration | `test_only_registered_slots_control_availability` | — | 통과 | 0.27 |
| integration | `test_retired_blackout_routes_do_not_create_or_remove_data` | §3.4 휴무일 | 통과 | 0.27 |
| integration | `test_outcome_requires_slot_started` | §3.4 상담 완료·미참석 | 통과 | 0.28 |
| integration | `test_staff_books_on_behalf_and_audit` | §2.1 교수자 대리 예약·감사 | 통과 | 0.23 |
| integration | `test_professor_cannot_self_book` | §2.1 교수자 본인 예약 불가 | 통과 | 0.21 |
| integration | `test_db_unavailable_returns_503` | §3.4 DB 장애 응답 | 통과 | 0.15 |
| integration | `test_staff_unbounded_bookings_include_distant_dates_and_filter_status` | — | 통과 | 0.28 |
| integration | `test_staff_can_move_student_without_reason` | — | 통과 | 0.22 |
| integration | `test_unknown_environment_is_rejected[prod]` | — | 통과 | 0.00 |
| integration | `test_unknown_environment_is_rejected[Production]` | — | 통과 | 0.00 |
| integration | `test_unknown_environment_is_rejected[staging]` | — | 통과 | 0.00 |
| integration | `test_unknown_environment_is_rejected[]` | — | 통과 | 0.00 |
| integration | `test_unknown_environment_is_rejected[production ]` | — | 통과 | 0.00 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[inactive-created]` | §2.1 권한표 | 통과 | 0.20 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[inactive-changed]` | §2.1 권한표 | 통과 | 0.25 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[inactive-cancelled]` | §2.1 권한표 | 통과 | 0.25 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[inactive-slot_changed]` | §2.1 권한표 | 통과 | 0.22 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[inactive-suggestion]` | §2.1 권한표 | 통과 | 0.24 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[student-created]` | §2.1 권한표 | 통과 | 0.22 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[student-changed]` | §2.1 권한표 | 통과 | 0.22 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[student-cancelled]` | §2.1 권한표 | 통과 | 0.23 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[student-slot_changed]` | §2.1 권한표 | 통과 | 0.21 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[student-suggestion]` | §2.1 권한표 | 통과 | 0.22 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[admin-created]` | §2.1 권한표 | 통과 | 0.25 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[admin-changed]` | §2.1 권한표 | 통과 | 0.58 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[admin-cancelled]` | §2.1 권한표 | 통과 | 0.26 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[admin-slot_changed]` | §2.1 권한표 | 통과 | 0.29 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[admin-suggestion]` | §2.1 권한표 | 통과 | 0.29 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[missing-created]` | §2.1 권한표 | 통과 | 0.23 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[missing-changed]` | §2.1 권한표 | 통과 | 0.23 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[missing-cancelled]` | §2.1 권한표 | 통과 | 0.21 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[missing-slot_changed]` | §2.1 권한표 | 통과 | 0.23 |
| integration | `test_all_gmail_kinds_recheck_professor_permission[missing-suggestion]` | §2.1 권한표 | 통과 | 0.23 |
| integration | `test_email_pause_after_claim_prevents_delivery` | — | 통과 | 0.24 |
| integration | `test_booking_refreshes_stale_slot_before_deadline_check` | — | 통과 | 0.21 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[None]` | — | 통과 | 0.07 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw1]` | — | 통과 | 0.06 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw2]` | — | 통과 | 0.07 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw3]` | — | 통과 | 0.07 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw4]` | — | 통과 | 0.06 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw5]` | — | 통과 | 0.08 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw6]` | — | 통과 | 0.07 |
| integration | `test_optional_external_analysis_bad_shapes_fall_back[raw7]` | — | 통과 | 0.08 |
| integration | `test_local_analysis_does_not_call_external_client` | §10 반복 의견 분석 | 통과 | 0.08 |
| integration | `test_delete_only_cancelled_slots_without_any_booking_history` | — | 통과 | 0.28 |
| integration | `test_other_creator_protected_and_admin_can_remove_empty` | — | 통과 | 0.21 |
| integration | `test_rescheduled_booking_history_also_prevents_delete` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.26 |
| integration | `test_public_board_defaults_private_and_staff_only_replies` | — | 통과 | 0.29 |
| integration | `test_suggestion_trash_restore_purge_and_permissions` | §2.1 권한표 | 통과 | 0.38 |
| integration | `test_survey_trash_protects_responses_and_cascades_only_on_confirmed_purge` | — | 통과 | 0.38 |
| integration | `test_consultation_exports_scope_options_and_injection` | — | 통과 | 0.38 |
| integration | `test_google_login_flow` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.44 |
| integration | `test_survey_return_is_signed_and_only_local_numeric_id` | — | 통과 | 0.11 |
| integration | `test_state_mismatch_rejected` | §7.2 OAuth state 검증 | 통과 | 0.08 |
| integration | `test_unverified_email_rejected` | §2.2 인증되지 않은 이메일 거부 | 통과 | 0.07 |
| integration | `test_identity_bound_to_sub_not_email` | §2.2 계정 ID 기준 식별 | 통과 | 0.10 |
| integration | `test_verifier_failure_is_401` | §7.2 ID 토큰 검증 실패 | 통과 | 0.09 |
| integration | `test_remember_duration_is_signed_and_logout_revokes_session[False]` | — | 통과 | 0.11 |
| integration | `test_remember_duration_is_signed_and_logout_revokes_session[True]` | — | 통과 | 0.11 |
| integration | `test_callback_document_commits_session_without_redirect_chain` | — | 통과 | 0.10 |
| integration | `test_exchange_failure_offers_fresh_login_without_token_leak` | — | 통과 | 0.09 |
| integration | `test_guest_cannot_publish_but_signed_in_student_can` | — | 통과 | 0.29 |
| integration | `test_spoofed_forwarded_for_shares_the_proxy_appended_bucket` | — | 통과 | 0.23 |
| integration | `test_client_address_uses_right_most_trusted_entries` | — | 통과 | 0.00 |
| integration | `test_health_does_not_touch_database_but_readiness_does` | — | 통과 | 0.18 |
| integration | `test_only_writes_wake_workers` | — | 통과 | 0.20 |
| integration | `test_completion_plans_actual_next_end` | — | 통과 | 0.22 |
| integration | `test_completion_waits_until_signal_and_stops_immediately` | — | 통과 | 0.07 |
| integration | `test_outbox_idle_retry_and_blocked_chains` | — | 통과 | 0.29 |
| integration | `test_push_plans_daily_and_thirty_minute_reminders` | — | 통과 | 0.35 |
| integration | `test_paused_mail_does_not_spin_on_expired_lease` | — | 통과 | 0.23 |
| integration | `test_completion_runs_at_due_timeout_without_foreground_request` | — | 통과 | 0.03 |
| integration | `test_completion_uses_same_scan_clock_across_end_boundary` | — | 통과 | 0.00 |
| integration | `test_notification_scan_clock_and_fast_failure_retry` | — | 통과 | 0.00 |
| integration | `test_summary_minimal_authorized_current_data` | — | 통과 | 0.30 |
| integration | `test_wrong_event_type_and_corrupt_keys_never_resolve` | — | 통과 | 0.29 |
| integration | `test_summary_lookup_is_batched_and_account_scoped` | — | 통과 | 0.33 |
| integration | `test_missing_deleted_event_no_false_booking` | — | 통과 | 0.30 |
| integration | `test_changed_summary_is_latest_not_invented_before_after` | — | 통과 | 0.30 |
| integration | `test_target_owned_booking_and_cancelled` | — | 통과 | 0.33 |
| integration | `test_legacy_missing_event_and_future_safe` | — | 통과 | 0.65 |
| integration | `test_reminder_body_and_suggestion_destination` | — | 통과 | 0.24 |
| integration | `test_disabled_anonymous_features_fail_closed_for_every_role` | — | 통과 | 0.22 |
| integration | `test_sqlite_upgrade_matches_models_and_downgrade` | §7.1 마이그레이션 (SQLite) | 통과 | 0.37 |
| integration | `test_feedback_migration_preserves_legacy_private_suggestions` | §7.1 마이그레이션 | 통과 | 0.17 |
| integration | `test_survey_access_migration_keeps_existing_survey_login_only` | §7.1 마이그레이션 | 통과 | 0.16 |
| integration | `test_expired_migration_preserves_referenced_booking` | §7.1 마이그레이션 | 통과 | 0.19 |
| integration | `test_book_change_cancel_and_minimal_named_mail` | — | 통과 | 0.25 |
| integration | `test_proxy_and_force_slot_cancel_and_slot_change` | — | 통과 | 0.27 |
| integration | `test_disabled_and_rejected_requests_do_not_enqueue` | — | 통과 | 0.24 |
| integration | `test_transaction_failure_rolls_back_booking_and_outbox` | — | 통과 | 0.18 |
| integration | `test_failures_do_not_reverse_successful_booking[pending-rate_limited]` | §5 남용 방지 (횟수 무제한·속도 제한) | 통과 | 0.23 |
| integration | `test_failures_do_not_reverse_successful_booking[reauth-token_rejected]` | — | 통과 | 0.26 |
| integration | `test_failures_do_not_reverse_successful_booking[uncertain-send_network_unknown]` | — | 통과 | 0.24 |
| integration | `test_failures_do_not_reverse_successful_booking[failed-send_rejected]` | — | 통과 | 0.24 |
| integration | `test_chain_order_crash_recovery_and_admin_review` | — | 통과 | 0.33 |
| integration | `test_retry_limit_and_no_secrets_in_admin_response` | — | 통과 | 0.28 |
| integration | `test_failed_reschedule_rolls_back_without_additional_notification` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.25 |
| integration | `test_professor_summary_is_scoped_and_student_denied` | — | 통과 | 0.25 |
| integration | `test_callback_access_log_strips_query_only` | — | 통과 | 0.00 |
| integration | `test_token_error_log_uses_fixed_categories[invalid_grant-invalid_grant]` | — | 통과 | 0.45 |
| integration | `test_token_error_log_uses_fixed_categories[SECRET-other]` | — | 통과 | 0.00 |
| integration | `test_personal_alerts_access_and_defaults` | — | 통과 | 0.27 |
| integration | `test_due_schedule_deduplicates_merges_and_rechecks_cancellations` | — | 통과 | 0.31 |
| integration | `test_booking_metadata_roundtrip_and_reschedule` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.23 |
| integration | `test_old_booking_payload_remains_compatible` | — | 통과 | 0.21 |
| integration | `test_survey_course_semester_create_edit_clone` | — | 통과 | 0.23 |
| integration | `test_production_dev_login_endpoint_is_disabled_even_with_staging` | — | 통과 | 0.07 |
| integration | `test_production_rejects_attempt_to_enable_dev_login` | — | 통과 | 0.00 |
| integration | `test_booking_inbox_without_external_channels` | — | 통과 | 0.29 |
| integration | `test_scoped_deduplicated_and_transactional` | — | 통과 | 0.24 |
| integration | `test_inactive_professor_gets_no_new_rows` | — | 통과 | 0.14 |
| integration | `test_inbox_migration_preserves_data_and_refuses_loss` | §7.1 마이그레이션 | 통과 | 0.17 |
| integration | `test_delayed_suggestion_not_visible_or_markable` | — | 통과 | 0.25 |
| integration | `test_admin_inbox_is_private_and_does_not_mark_professors_read` | — | 통과 | 0.33 |
| integration | `test_admin_suggestion_immediate_and_permission_revocation` | §2.1 권한표 | 통과 | 0.23 |
| integration | `test_inactive_admin_gets_no_new_notices_or_access` | — | 통과 | 0.21 |
| integration | `test_arrival_order_ties_and_future_boundary[prof]` | — | 통과 | 0.23 |
| integration | `test_arrival_order_ties_and_future_boundary[admin]` | — | 통과 | 0.23 |
| integration | `test_cursor_reaches_old_unread_and_stays_stable_after_new_arrival[prof]` | — | 통과 | 0.34 |
| integration | `test_cursor_reaches_old_unread_and_stays_stable_after_new_arrival[admin]` | — | 통과 | 0.42 |
| integration | `test_midnight_arrival_date_is_not_enqueue_day` | — | 통과 | 0.73 |
| integration | `test_second_precision_order_within_displayed_minute` | — | 통과 | 0.28 |
| integration | `test_read_all_is_private_available_only_and_idempotent[prof]` | — | 통과 | 0.26 |
| integration | `test_read_all_is_private_available_only_and_idempotent[admin]` | — | 통과 | 0.30 |
| integration | `test_direct_login_without_consent_and_no_fabricated_consent[]` | — | 통과 | 0.12 |
| integration | `test_direct_login_without_consent_and_no_fabricated_consent[?consent_version=old&notice_ack=yes&transfer_ack=yes]` | — | 통과 | 0.11 |
| integration | `test_no_consent_flow_preserves_oauth_request_validation[missing_cookie]` | — | 통과 | 0.13 |
| integration | `test_no_consent_flow_preserves_oauth_request_validation[tampered_cookie]` | — | 통과 | 0.09 |
| integration | `test_no_consent_flow_preserves_oauth_request_validation[wrong_state]` | — | 통과 | 0.10 |
| integration | `test_no_consent_flow_preserves_oauth_request_validation[missing_code]` | — | 통과 | 0.07 |
| integration | `test_public_notice_escapes_operator_and_hides_when_disabled` | — | 통과 | 0.08 |
| integration | `test_operator_required_when_notice_enabled` | — | 통과 | 0.00 |
| integration | `test_anonymous_submit_dedup_and_no_account_link` | — | 통과 | 0.31 |
| integration | `test_anonymous_availability_share_and_mode_lock` | — | 통과 | 0.34 |
| integration | `test_scale_labels_and_login_mode_preserved` | — | 통과 | 0.24 |
| integration | `test_logged_in_student_lists_anonymous_surveys_without_account_participation` | — | 통과 | 0.32 |
| integration | `test_push_restricted_and_minimal_payload_and_logout` | — | 통과 | 0.36 |
| integration | `test_push_rejects_arbitrary_destinations[http://fcm.googleapis.com/fcm/send/x]` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.24 |
| integration | `test_push_rejects_arbitrary_destinations[https://127.0.0.1/fcm/send/x]` | — | 통과 | 0.23 |
| integration | `test_push_rejects_arbitrary_destinations[https://fcm.googleapis.com.evil.test/fcm/send/x]` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.22 |
| integration | `test_push_rejects_arbitrary_destinations[https://user@fcm.googleapis.com/fcm/send/x]` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.21 |
| integration | `test_push_rejects_arbitrary_destinations[https://fcm.googleapis.com:444/fcm/send/x]` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.21 |
| integration | `test_push_rejects_arbitrary_destinations[https://fcm.googleapis.com/other/x]` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.20 |
| integration | `test_pending_push_is_skipped_after_access_revoked[logout]` | — | 통과 | 0.85 |
| integration | `test_pending_push_is_skipped_after_access_revoked[expired]` | — | 통과 | 0.28 |
| integration | `test_pending_push_is_skipped_after_access_revoked[role]` | — | 통과 | 0.28 |
| integration | `test_gmail_reauth_does_not_block_push_and_unknown_not_retried` | — | 통과 | 0.29 |
| integration | `test_real_webpush_encryption_with_mock_http` | — | 통과 | 0.27 |
| integration | `test_installation_assets_and_root_worker` | — | 통과 | 0.24 |
| integration | `test_installation_does_not_grant_student_staff_access` | — | 통과 | 0.22 |
| integration | `test_notification_worker_links_are_fixed_authenticated_routes` | — | 통과 | 0.23 |
| integration | `test_editorial_icons_and_apple_home_screen` | — | 통과 | 0.26 |
| integration | `test_far_future_visible_for_rescheduling_only` | — | 통과 | 0.26 |
| integration | `test_available_days_requires_login` | — | 통과 | 0.10 |
| integration | `test_far_future_change_keeps_booking_id` | — | 통과 | 0.21 |
| integration | `test_move_keeps_identity_metadata_notes_and_single_change_notice` | — | 통과 | 0.22 |
| integration | `test_stale_move_rejected_without_second_transfer` | — | 통과 | 0.23 |
| integration | `test_failure_after_move_rolls_back_identity_history_and_seats` | — | 통과 | 0.21 |
| integration | `test_restore_pipeline_refuses_unsafe_or_failed_operations[success]` | — | 통과 | 0.05 |
| integration | `test_restore_pipeline_refuses_unsafe_or_failed_operations[wrong_host]` | — | 통과 | 0.03 |
| integration | `test_restore_pipeline_refuses_unsafe_or_failed_operations[occupied]` | — | 통과 | 0.04 |
| integration | `test_restore_pipeline_refuses_unsafe_or_failed_operations[decrypt_fail]` | — | 통과 | 0.04 |
| integration | `test_restore_pipeline_refuses_unsafe_or_failed_operations[restore_fail]` | — | 통과 | 0.05 |
| integration | `test_reports_overdue_records_without_changing_anything` | — | 통과 | 0.20 |
| integration | `test_public_site_qr_uses_configured_url_without_account_or_request_host[svg]` | — | 통과 | 0.22 |
| integration | `test_public_site_qr_uses_configured_url_without_account_or_request_host[png]` | — | 통과 | 0.22 |
| integration | `test_preview_and_replace_only_unbooked_slots` | — | 통과 | 0.20 |
| integration | `test_replace_protects_any_booked_slot_and_preserves_booking` | — | 통과 | 0.20 |
| integration | `test_student_cannot_preview_or_replace_slots` | — | 통과 | 0.16 |
| integration | `test_policy_endpoint_reflects_admin_settings` | — | 통과 | 0.21 |
| integration | `test_professor_dashboard_groups_records_and_keeps_private_notes` | — | 통과 | 0.93 |
| integration | `test_dashboard_restricts_all_study_data_to_staff` | — | 통과 | 0.21 |
| integration | `test_notes_filter_requires_actual_note_and_query_is_literal` | — | 통과 | 0.23 |
| integration | `test_staff_insights_validates_query_ranges` | — | 통과 | 0.18 |
| integration | `test_overview_period_includes_upcoming_bookings` | — | 통과 | 0.20 |
| integration | `test_future_deadline_planned_even_without_external_channels` | — | 통과 | 0.14 |
| integration | `test_scheduled_push_rechecks_authoritative_recipient_and_permission[none]` | §2.1 권한표 | 통과 | 0.26 |
| integration | `test_scheduled_push_rechecks_authoritative_recipient_and_permission[role]` | §2.1 권한표 | 통과 | 0.30 |
| integration | `test_scheduled_push_rechecks_authoritative_recipient_and_permission[optout]` | §2.1 권한표 | 통과 | 0.28 |
| integration | `test_scheduled_push_rechecks_authoritative_recipient_and_permission[wrong-recipient]` | §2.1 권한표 | 통과 | 0.27 |
| integration | `test_independent_scheduled_messages_not_blocked_by_old_uncertain_chain` | — | 통과 | 0.26 |
| integration | `test_create_scope_idempotence_validation_and_cancel` | — | 통과 | 0.28 |
| integration | `test_due_private_offline_idempotent_and_no_external` | — | 통과 | 0.23 |
| integration | `test_role_revocation_suppresses_due` | — | 통과 | 0.25 |
| integration | `test_due_failure_rolls_back_marker_and_inbox` | — | 통과 | 0.22 |
| integration | `test_additive_migration_preserves_inbox_and_guards_reminders` | §7.1 마이그레이션 | 통과 | 0.18 |
| integration | `test_staging_mode_requires_explicit_allowlist` | — | 통과 | 0.00 |
| integration | `test_staging_bootstrap_allows_no_google_credentials_but_not_partial_oauth` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.00 |
| integration | `test_only_staging_approved_google_accounts_can_sign_in` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.09 |
| integration | `test_direct_database_url_used_for_migrations` | §7.1 마이그레이션 | 통과 | 1.01 |
| integration | `test_staging_admin_rebind_preserves_identity_and_revokes_session` | — | 통과 | 0.11 |
| integration | `test_normal_environment_does_not_merge_different_identities` | — | 통과 | 0.10 |
| integration | `test_existing_session_cannot_bypass_new_staging_allowlist` | — | 통과 | 0.20 |
| integration | `test_development_mode_without_staging_keeps_existing_sessions` | — | 통과 | 0.11 |
| integration | `test_removed_role_cannot_cancel_booking_or_change_note[admin-admin@test.ac.kr]` | — | 통과 | 0.24 |
| integration | `test_removed_role_cannot_cancel_booking_or_change_note[prof-prof@test.ac.kr]` | — | 통과 | 0.23 |
| integration | `test_removed_role_cannot_cancel_booking_or_change_note[s1-s1@test.ac.kr]` | — | 통과 | 0.22 |
| integration | `test_empty_runtime_allowlist_denies_existing_session` | — | 통과 | 0.10 |
| integration | `test_static_js_and_html_are_revalidated_after_deploy` | — | 통과 | 0.16 |
| integration | `test_student_updates_ownership_notes_and_racing_ack` | — | 통과 | 0.30 |
| integration | `test_self_booking_does_not_raise_staff_update` | §2.1 교수자 본인 예약 불가 | 통과 | 0.23 |
| integration | `test_anonymous_receipt_private_reply_and_trash` | — | 통과 | 1.02 |
| integration | `test_anonymous_notices_without_content_or_identity` | — | 통과 | 0.14 |
| integration | `test_notice_failure_rolls_back_submission` | — | 통과 | 0.12 |
| integration | `test_no_notice_to_nonprofessor_or_paused_email` | — | 통과 | 0.13 |
| integration | `test_suggestion_push_is_generic_and_rechecks_professor[False]` | — | 통과 | 0.24 |
| integration | `test_suggestion_push_is_generic_and_rechecks_professor[True]` | — | 통과 | 0.27 |
| integration | `test_suggestion_email_rechecks_professor_before_network` | — | 통과 | 0.15 |
| integration | `test_uncertain_suggestion_does_not_block_next` | — | 통과 | 0.17 |
| integration | `test_immediate_new_notice_preserves_legacy_delayed_queue` | — | 통과 | 0.18 |
| integration | `test_paused_email_stays_paused_with_immediate_inbox` | — | 통과 | 0.13 |
| integration | `test_staff_search_is_literal_scoped_and_does_not_expose_private_to_student` | — | 통과 | 0.26 |
| integration | `test_date_sort_preserves_same_day_uuid_order_and_pagination` | — | 통과 | 0.22 |
| integration | `test_empty_trash_scope_snapshot_and_private_audit[prof]` | — | 통과 | 0.24 |
| integration | `test_empty_trash_scope_snapshot_and_private_audit[admin]` | — | 통과 | 0.28 |
| integration | `test_empty_trash_rejects_restore_race_and_duplicates_atomically` | — | 통과 | 0.23 |
| integration | `test_empty_trash_requires_role_confirmation_csrf_and_feature` | §7.2 CSRF 방어 | 통과 | 0.24 |
| integration | `test_delete_selected_trash_preserves_unselected_and_new_rows[prof]` | — | 통과 | 0.22 |
| integration | `test_delete_selected_trash_preserves_unselected_and_new_rows[admin]` | — | 통과 | 0.24 |
| integration | `test_delete_selected_rejects_changed_selection_atomically[restored]` | — | 통과 | 0.21 |
| integration | `test_delete_selected_rejects_changed_selection_atomically[missing]` | — | 통과 | 0.20 |
| integration | `test_delete_selected_rejects_changed_selection_atomically[active]` | — | 통과 | 0.27 |
| integration | `test_delete_selected_validates_permission_csrf_and_request` | §7.2 CSRF 방어 | 통과 | 0.25 |
| integration | `test_submit_and_read` | §5 건의 제출·열람 | 통과 | 0.24 |
| integration | `test_no_author_stored` | §5 건의 작성자 미저장 | 통과 | 0.20 |
| integration | `test_rate_limit_blocks_bursts_not_total` | §5 남용 방지 (횟수 무제한·속도 제한) | 통과 | 0.25 |
| integration | `test_content_validation` | §5 악성·과대 입력 | 통과 | 0.22 |
| integration | `test_html_stored_as_text` | §7.2 XSS 방어 | 통과 | 0.22 |
| integration | `test_local_analysis` | §10 반복 의견 분석 | 통과 | 0.25 |
| integration | `test_consultation_notes_never_reach_analysis` | §10 상담 기록 외부 AI 미전송·PII 마스킹 | 통과 | 0.28 |
| integration | `test_external_ai_hallucinated_refs_dropped_and_failure_fallback` | §10 근거 없는 AI 결과 제거·장애 시 기본 기능 유지 | 통과 | 0.23 |
| integration | `test_ai_disabled` | §10 AI 비활성화 | 통과 | 0.22 |
| integration | `test_anonymous_writer_and_protected_board` | — | 통과 | 0.34 |
| integration | `test_private_support_ownership_every_endpoint` | — | 통과 | 0.38 |
| integration | `test_support_conversation_status_and_unread_race` | — | 통과 | 0.32 |
| integration | `test_support_validates_content_path_csrf_and_limits` | §7.2 CSRF 방어 | 통과 | 0.34 |
| integration | `test_full_survey_flow` | §4 설문 제출·통계 | 통과 | 1.05 |
| integration | `test_duplicate_submission_blocked` | §4.2 중복 참여 방지 | 통과 | 0.21 |
| integration | `test_answer_validation` | §8 설문 입력값 검증 | 통과 | 0.22 |
| integration | `test_questions_locked_after_publish_and_duplicate` | §4.1 게시 후 문항 수정 정책 | 통과 | 0.24 |
| integration | `test_draft_not_visible_and_closed_not_submittable` | §4.1 게시·종료 상태 | 통과 | 0.23 |
| integration | `test_question_validation` | §8 설문 입력값 검증 | 통과 | 0.18 |
| integration | `test_export_xlsx_sanitizes_formulas` | §7.2 엑셀 수식 주입 방어 | 통과 | 0.24 |
| integration | `test_anonymity_schema_has_no_link` | §4.2 익명 응답 분리 | 통과 | 0.06 |
| integration | `test_staff_cannot_see_who_participated` | §4.2 개인별 참여 여부 비공개 | 통과 | 0.23 |
| integration | `test_no_submission_audit_or_log` | §4.2 로그·감사기록에 익명 제출 미기록 | 통과 | 0.23 |
| integration | `test_feature_flag_disables_surveys` | §4.2 검토 전 비활성화 스위치 | 통과 | 0.12 |
| integration | `test_reschedule_checks_both_thirty_minute_boundaries[1800-3600-True]` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.21 |
| integration | `test_reschedule_checks_both_thirty_minute_boundaries[1799-3600-False]` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.21 |
| integration | `test_reschedule_checks_both_thirty_minute_boundaries[3600-1800-True]` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.22 |
| integration | `test_reschedule_checks_both_thirty_minute_boundaries[3600-1799-False]` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.25 |
| integration | `test_cancel_at_exact_thirty_minutes` | — | 통과 | 0.24 |
| postgres | `test_calendar_waiter_rechecks_after_commit[lecture]` | — | 건너뜀 | 0.00 |
| postgres | `test_calendar_waiter_rechecks_after_commit[booking]` | — | 건너뜀 | 0.00 |
| postgres | `test_simultaneous_lecture_vs_booking_preserves_consultation` | — | 건너뜀 | 0.00 |
| postgres | `test_simultaneous_overlapping_lectures_one_winner` | §3.4 시간표 충돌 | 건너뜀 | 0.00 |
| postgres | `test_populated_lecture_downgrade_refuses_data_loss` | — | 건너뜀 | 0.00 |
| postgres | `test_notification_last_seat_and_worker_claim_race` | — | 건너뜀 | 0.00 |
| postgres | `test_account_delete_vs_booking_preserves_references` | — | 건너뜀 | 0.00 |
| postgres | `test_slot_cancel_vs_student_action_has_no_duplicate_alert[False]` | — | 건너뜀 | 0.00 |
| postgres | `test_slot_cancel_vs_student_action_has_no_duplicate_alert[True]` | — | 건너뜀 | 0.00 |
| postgres | `test_announcement_concurrent_publish_has_one_winner[0]` | — | 건너뜀 | 0.00 |
| postgres | `test_announcement_concurrent_publish_has_one_winner[1]` | — | 건너뜀 | 0.00 |
| postgres | `test_anonymous_survey_concurrent_duplicate` | — | 건너뜀 | 0.00 |
| postgres | `test_migration_matches_models_and_downgrades` | §7.1 마이그레이션 | 건너뜀 | 0.00 |
| postgres | `test_concurrent_open_slot_creation_cannot_overlap` | §3.4 시간표 충돌 | 건너뜀 | 0.00 |
| postgres | `test_replacing_unbooked_slots_preserves_postgres_overlap_constraint` | §3.4 시간표 충돌 | 건너뜀 | 0.00 |
| postgres | `test_database_rejects_overlapping_open_slots` | §3.4 시간표 충돌 | 건너뜀 | 0.00 |
| postgres | `test_concurrent_last_seat_individual` | §3.4 동시 마지막 자리 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_concurrent_group_capacity` | §3.4 단체 정원 동시성 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_same_student_double_booking_race` | §3.3 1인 1예약 동시성 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_reschedule_vs_booking_race` | §3.4 변경 실패 시 기존 예약 보존 | 건너뜀 | 0.00 |
| postgres | `test_concurrent_survey_double_submit` | §4.2 동시 중복 제출 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_concurrent_cross_demotion_keeps_an_admin` | §2.2 동시 상호 강등 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_capacity_check_constraint_enforced_by_db` | §3.3 DB CHECK 제약 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_service_conflict_type` | 내부 일관성 | 건너뜀 | 0.00 |
| postgres | `test_supabase_api_roles_have_no_access` | §7.2 Supabase 공개 API 권한 회수 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_every_public_table_has_rls` | §7.2 전 테이블 RLS (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_anon_role_is_denied_in_practice` | §7.2 anon 실제 조회 거부 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_future_tables_get_no_api_grants` | §7.2 새 테이블 기본 권한 회수 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_app_still_works_with_rls` | §7.2 RLS 적용 후 앱 정상 동작 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_non_superuser_owner_bypasses_rls` | §7.2 비슈퍼유저 소유자 RLS 우회 (PostgreSQL) | 건너뜀 | 0.00 |
| postgres | `test_cancelled_slot_delete_race_has_one_winner` | — | 건너뜀 | 0.00 |
| postgres | `test_historical_expiry_upgrade_preserves_refs_and_unique_seat_rule` | — | 건너뜀 | 0.00 |
| postgres | `test_concurrent_same_booking_moves_preserve_identity_and_reject_stale` | — | 건너뜀 | 0.00 |
| postgres | `test_concurrent_moves_to_last_seat_keep_losing_booking` | — | 건너뜀 | 0.00 |
| postgres | `test_populated_inbox_migration_refuses_data_loss` | §7.1 마이그레이션 | 건너뜀 | 0.00 |
| postgres | `test_private_reminder_concurrent_dispatch_exactly_once` | — | 건너뜀 | 0.00 |
| postgres | `test_private_reminder_cancel_vs_dispatch_is_atomic` | — | 건너뜀 | 0.00 |
| postgres | `test_new_booking_rechecks_staff_time_edit_after_slot_lock` | — | 건너뜀 | 0.00 |
| postgres | `test_selected_delete_vs_restore_is_atomic` | — | 건너뜀 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[text-bg]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[muted-bg]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[muted-panel]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[primary-bg]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[primary-primary-weak]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[danger-danger-weak]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[mine-mine-weak]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[available-available-bg]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[lecture-text-lecture-bg]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_normal_text_palette_meets_wcag_aa[lecture-text-lecture-hover]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_filled_buttons_have_legible_white_text[primary]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_filled_buttons_have_legible_white_text[booking-mine]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_filled_buttons_have_legible_white_text[mine]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_filled_buttons_have_legible_white_text[danger]` | — | 통과 | 0.00 |
| test_editorial_palette | `test_focus_and_input_boundaries_have_three_to_one_contrast` | — | 통과 | 0.00 |
| test_lecture_review | `test_recurrence_conflict_rolls_back_all_occurrences` | — | 통과 | 0.25 |
| test_lecture_review | `test_reschedule_into_lecture_updates_booking_and_counts` | §3.4 변경 실패 시 기존 예약 보존 | 통과 | 0.33 |
| test_lecture_review | `test_student_cannot_change_or_cancel_lecture` | — | 통과 | 0.29 |
| test_lecture_review | `test_staff_proxy_booking_uses_registered_consultation` | — | 통과 | 0.28 |
| test_lecture_review | `test_lecture_update_into_booked_slot_preserves_both` | — | 통과 | 0.28 |
| test_lecture_review | `test_full_target_under_lecture_preserves_original_booking` | — | 통과 | 0.30 |
| test_lectures | `test_lecture_roles_and_weekly` | — | 통과 | 0.28 |
| test_lectures | `test_registered_consultation_overrides_lecture` | — | 통과 | 0.29 |
| test_lectures | `test_existing_booking_prevents_lecture` | — | 통과 | 0.26 |
| test_lectures | `test_boundary_and_soft_cancel` | — | 통과 | 0.26 |
| test_lectures | `test_invalid_time_and_title` | — | 통과 | 0.23 |
| test_lectures | `test_priority_preserves_capacity_and_staff_booking` | — | 통과 | 0.27 |
| test_student_lecture_calendar | `test_student_lecture_calendar_read_only_minimal_fields` | — | 통과 | 0.28 |
| test_weekday_policy | `test_kst_whole_interval[2026-11-20T14:00:00Z-2026-11-20T15:00:00Z-False]` | — | 통과 | 0.00 |
| test_weekday_policy | `test_kst_whole_interval[2026-11-20T14:00:00Z-2026-11-20T15:01:00Z-True]` | — | 통과 | 0.00 |
| test_weekday_policy | `test_kst_whole_interval[2026-11-20T16:00:00Z-2026-11-20T17:00:00Z-True]` | — | 통과 | 0.00 |
| test_weekday_policy | `test_kst_whole_interval[2026-11-22T15:00:00Z-2026-11-22T16:00:00Z-False]` | — | 통과 | 0.00 |
| test_weekday_policy | `test_kst_whole_interval[2026-11-20T12:00:00Z-2026-11-23T03:00:00Z-True]` | — | 통과 | 0.00 |
| test_weekday_policy | `test_weekend_slot_create_preview_replace_rejected_atomically` | — | 통과 | 0.18 |
| test_weekday_policy | `test_weekday_create_and_weekend_move_blocked` | — | 통과 | 1.03 |
| test_weekday_policy | `test_legacy_weekend_query_cancel_and_new_bookings_blocked` | — | 통과 | 0.36 |
| unit | `test_refresh_cache_sender_scope_and_minimal_message` | — | 통과 | 0.00 |
| unit | `test_refresh_rejection_never_sends[400-reauth]` | — | 통과 | 0.00 |
| unit | `test_refresh_rejection_never_sends[429-pending]` | — | 통과 | 0.00 |
| unit | `test_refresh_rejection_never_sends[503-pending]` | — | 통과 | 0.00 |
| unit | `test_scope_must_be_attested_and_send_only[]` | — | 통과 | 0.00 |
| unit | `test_scope_must_be_attested_and_send_only[https://www.googleapis.com/auth/gmail.send https://mail.google.com/]` | §2.2·§7.2 Google 로그인 흐름 (가짜 검증기) | 통과 | 0.00 |
| unit | `test_scope_must_be_attested_and_send_only[openid]` | — | 통과 | 0.00 |
| unit | `test_send_errors[429-pending]` | — | 통과 | 0.00 |
| unit | `test_send_errors[500-uncertain]` | — | 통과 | 0.00 |
| unit | `test_send_errors[403-reauth]` | — | 통과 | 0.00 |
| unit | `test_send_errors[400-failed]` | — | 통과 | 0.00 |
| unit | `test_timeout_after_send_is_uncertain` | — | 통과 | 0.00 |
| unit | `test_recipient_change_cannot_redirect_existing_mail` | — | 통과 | 0.00 |
| unit | `test_configuration_separation_and_header_injection` | — | 통과 | 0.00 |
| unit | `test_push_config_requires_matching_keys_and_private_value_is_redacted` | — | 통과 | 0.00 |
| unit | `test_push_disabled_needs_no_secret` | — | 통과 | 0.00 |
| unit | `test_approved_isolated_destination` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[EXPECTED_RESTORE_HOST-other.example]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[EXPECTED_RESTORE_DATABASE-other_restore]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[DATABASE_URL_DIRECT-postgresql://localhost/neondb]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[DATABASE_URL_DIRECT-postgresql://source-pooler.example/neondb]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[RESTORE_DATABASE_URL-postgresql://localhost/classbridge_restore_trial?host=source.example]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[RESTORE_DATABASE_URL-postgresql://localhost/classbridge_restore_trial?options=-csearch_path=public]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[RESTORE_DATABASE_URL-postgresql://localhost/classbridge_restore_trial?dbname=neondb]` | — | 통과 | 0.00 |
| unit | `test_wrong_or_overridden_destination_is_refused[RESTORE_DATABASE_URL-host=source.example dbname=neondb]` | — | 통과 | 0.00 |
| unit | `test_missing_confirmation_is_refused[DATABASE_URL_DIRECT]` | — | 통과 | 0.00 |
| unit | `test_missing_confirmation_is_refused[RESTORE_DATABASE_URL]` | — | 통과 | 0.00 |
| unit | `test_missing_confirmation_is_refused[EXPECTED_RESTORE_HOST]` | — | 통과 | 0.01 |
| unit | `test_missing_confirmation_is_refused[EXPECTED_RESTORE_DATABASE]` | — | 통과 | 0.00 |
| unit | `test_database_name_is_not_only_a_substring` | — | 통과 | 0.01 |
| unit | `test_connection_parse_error_never_includes_password` | — | 통과 | 0.00 |
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
| unit | `test_rescheduling_ignores_only_booking_window` | — | 통과 | 0.00 |
