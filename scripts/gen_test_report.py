"""JUnit XML(pytest --junitxml)에서 docs/test-report.md 의 결과 표를 생성한다.

실행: python scripts/gen_test_report.py test-results.xml
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 테스트 이름 키워드 → 검증 대상 요구사항 (지시서 절 번호)
REQ = [
    ("every_api_route_declares_permission", "§2.3 기본 거부: 모든 API 권한 선언"),
    ("unauthenticated", "§2.3 미로그인 거부"),
    ("student_cannot_call_professor", "§2.3 학생→교수자 API 거부"),
    ("student_cannot_call_admin", "§2.3 학생→관리자 API 거부"),
    ("professor_cannot_use_admin", "§2.3 교수자→관리자 설정 거부"),
    ("admin_can_use_all_professor", "§2.3 관리자의 교수자 기능 허용"),
    ("other_students_booking", "§2.3 타인 예약 조회·수정·취소 거부"),
    ("hides_notes", "§7.2 상담 기록 열람 권한"),
    ("revoked_admin_session", "§2.3 권한 회수 후 기존 세션 거부"),
    ("role_tampering", "§2.3 브라우저 역할 조작 무효"),
    ("csrf", "§7.2 CSRF 방어"),
    ("security_headers", "§7.2 보안 헤더"),
    ("cookie_flags", "§7.2 안전한 쿠키"),
    ("bootstrap_roles", "§2.2 초기 관리자·교수 등록"),
    ("own_role", "§2.2 자기 권한 변경 차단"),
    ("last_admin", "§2.2 유일한 관리자 보호"),
    ("deactivation", "§2.2 계정 비활성화·세션 무효화"),
    ("role_change_is_audited", "§2.2 권한 변경 기록"),
    ("env_allowlist", "§2.2 최초 관리자 부여 절차 보호"),
    ("settings_update", "§3.3 관리자 설정 변경"),
    ("domain_restriction", "§2.2 허용 도메인"),
    ("student_flow", "§3.1 학생 예약·조회·취소"),
    ("one_active_booking", "§3.3 1인 1활성 예약"),
    ("duplicate_click", "§3.4 중복 클릭"),
    ("double_click", "§3.4 중복 클릭 (브라우저)"),
    ("capacity_and_group", "§3.3 개인·단체 정원, 남은 자리"),
    ("individual_requires", "§3.2 개인 상담 정원"),
    ("cancel_deadline", "§3.3 취소 3시간 전 제한"),
    ("booking_deadline", "§3.3 예약 마감·예약 가능 범위"),
    ("reschedule", "§3.4 변경 실패 시 기존 예약 보존"),
    ("cancel_then_other", "§3.4 취소 직후 다른 학생 예약"),
    ("drop_below_booked", "§3.4 정원 축소 시 초과 방지"),
    ("slot_with_bookings", "§3.4 예약된 시간대 삭제"),
    ("overlap", "§3.4 시간표 충돌"),
    ("break_and_repeat", "§3.2 휴식·반복 일정"),
    ("blackout", "§3.4 휴무일"),
    ("outcome", "§3.4 상담 완료·미참석"),
    ("completes_consultation", "§3.4 상담 완료 (브라우저)"),
    ("on_behalf", "§2.1 교수자 대리 예약·감사"),
    ("self_book", "§2.1 교수자 본인 예약 불가"),
    ("db_unavailable", "§3.4 DB 장애 응답"),
    ("full_survey_flow", "§4 설문 제출·통계"),
    ("duplicate_submission", "§4.2 중복 참여 방지"),
    ("answer_validation", "§8 설문 입력값 검증"),
    ("locked_after_publish", "§4.1 게시 후 문항 수정 정책"),
    ("draft_not_visible", "§4.1 게시·종료 상태"),
    ("question_validation", "§8 설문 입력값 검증"),
    ("export_xlsx", "§7.2 엑셀 수식 주입 방어"),
    ("anonymity_schema", "§4.2 익명 응답 분리"),
    ("who_participated", "§4.2 개인별 참여 여부 비공개"),
    ("no_submission_audit", "§4.2 로그·감사기록에 익명 제출 미기록"),
    ("feature_flag", "§4.2 검토 전 비활성화 스위치"),
    ("submit_and_read", "§5 건의 제출·열람"),
    ("no_author_stored", "§5 건의 작성자 미저장"),
    ("rate_limit", "§5 남용 방지 (횟수 무제한·속도 제한)"),
    ("content_validation", "§5 악성·과대 입력"),
    ("html_stored_as_text", "§7.2 XSS 방어"),
    ("local_analysis", "§10 반복 의견 분석"),
    ("consultation_notes_never", "§10 상담 기록 외부 AI 미전송·PII 마스킹"),
    ("hallucinated", "§10 근거 없는 AI 결과 제거·장애 시 기본 기능 유지"),
    ("ai_disabled", "§10 AI 비활성화"),
    ("google", "§2.2·§7.2 Google 로그인 흐름 (가짜 검증기)"),
    ("state_mismatch", "§7.2 OAuth state 검증"),
    ("unverified_email", "§2.2 인증되지 않은 이메일 거부"),
    ("bound_to_sub", "§2.2 계정 ID 기준 식별"),
    ("verifier_failure", "§7.2 ID 토큰 검증 실패"),
    ("migration", "§7.1 마이그레이션"),
    ("sqlite_upgrade", "§7.1 마이그레이션 (SQLite)"),
    ("concurrent_last_seat", "§3.4 동시 마지막 자리 (PostgreSQL)"),
    ("concurrent_group", "§3.4 단체 정원 동시성 (PostgreSQL)"),
    ("double_booking_race", "§3.3 1인 1예약 동시성 (PostgreSQL)"),
    ("reschedule_vs_booking", "§3.4 변경·예약 경쟁 (PostgreSQL)"),
    ("survey_double_submit", "§4.2 동시 중복 제출 (PostgreSQL)"),
    ("cross_demotion", "§2.2 동시 상호 강등 (PostgreSQL)"),
    ("check_constraint", "§3.3 DB CHECK 제약 (PostgreSQL)"),
    ("suggestion_flow", "§5 건의 제출→열람 (브라우저)"),
    ("survey_create_submit", "§4 설문 생성→제출→통계 (브라우저)"),
    ("admin_uses_professor", "§2.1 관리자 교수자 기능·권한 변경 (브라우저)"),
    ("booking_flow_pc", "§3.1 학생 예약 흐름 PC (브라우저)"),
    ("mobile_student", "§3.1 모바일 예약·건의 (브라우저)"),
    ("mobile_professor", "§3.1 모바일 교수자 화면 (브라우저)"),
    ("permission", "§2.1 권한표"),
    ("admin_is_superset", "§2.1 Admin ⊇ Professor"),
    ("deanonymization", "§2.1 역추적 권한 부재"),
    ("unknown_role", "§2.3 알 수 없는 역할 거부"),
    ("generate_blocks", "§3.2 시간 블록 생성"),
    ("expand_days", "§3.2 반복 요일"),
    ("transitions", "§8 예약 상태 전환"),
    ("validate_answers", "§8 설문 입력값"),
    ("validate_questions", "§8 문항 검증"),
    ("excel_sanitize", "§7.2 엑셀 수식 주입"),
    ("scrub_pii", "§10 개인정보 마스킹"),
    ("rate_limiter", "§7.2 요청 제한"),
    ("access_log_filter", "§4.2 익명 제출 접근 로그 차단"),
    ("production_config", "§9 운영 설정 안전장치"),
    ("staff_has_no", "§2.1 권한표"),
    ("student_has_no", "§2.1 권한표"),
    ("professor_lacks", "§2.1 권한표"),
    ("service_conflict", "내부 일관성"),
]


def req_for(name: str) -> str:
    for key, req in REQ:
        if key in name:
            return req
    return "—"


def main(path: str) -> None:
    tree = ET.parse(path)
    rows, layers = [], Counter()
    for tc in tree.iter("testcase"):
        cls = tc.get("classname", "")
        layer = cls.split(".")[1] if cls.count(".") >= 1 else cls
        status = "통과"
        if tc.find("failure") is not None or tc.find("error") is not None:
            status = "실패"
        elif tc.find("skipped") is not None:
            status = "건너뜀"
        layers[(layer, status)] += 1
        rows.append((layer, tc.get("name"), req_for(tc.get("name")), status, float(tc.get("time", 0))))
    out = ["| 계층 | 테스트 | 검증 요구사항 | 결과 | 시간(s) |", "|---|---|---|---|---|"]
    for layer, name, req, status, t in rows:
        out.append(f"| {layer} | `{name}` | {req} | {status} | {t:.2f} |")
    summary = ", ".join(f"{k[0]} {k[1]} {v}" for k, v in sorted(layers.items()))
    (ROOT / "docs/test-results-table.md").write_text(
        f"# 자동 테스트 결과표 (자동 생성)\n\n요약: {summary}\n\n" + "\n".join(out) + "\n", encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test-results.xml")
