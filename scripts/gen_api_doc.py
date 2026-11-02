"""OpenAPI 스키마에서 docs/api.md 를 생성한다 (라우트 권한은 코드에서 직접 추출).

실행: python scripts/gen_api_doc.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.routing import APIRoute  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
KO = {
    "index": "웹 화면", "audit": "관리 작업 이력 조회", "get_settings": "운영 설정 조회", "put_settings": "운영 설정 변경",
    "list_users": "사용자 목록", "change_active": "계정 활성/비활성", "change_role": "역할 변경 (자기 자신·마지막 관리자 불가)",
    "analyze": "의견 분석 (로컬/외부 AI)", "list_blackouts": "상담 불가일 목록", "add_blackout": "상담 불가일 등록",
    "remove_blackout": "상담 불가일 삭제", "my_bookings": "내 예약 목록 (상담 기록 제외)",
    "create_booking": "예약 생성 (student_id는 교수자·관리자만)", "cancel_booking": "예약 취소 (학생: 3시간 전까지, 교수자: 사유 필수)",
    "reschedule_booking": "예약 변경 (원자적, 실패 시 기존 예약 유지)", "search_bookings": "예약 현황 조회",
    "set_outcome": "완료/미참석 처리", "set_note": "상담 기록 저장", "history": "예약 변경 이력", "list_students": "대리 예약용 학생 목록",
    "list_slots": "상담 시간표 조회", "create_slots": "상담 시간 일괄 생성 (반복·휴식·휴무일 제외)",
    "update_slot": "상담 시간 수정 (정원 축소 제한)", "cancel_slot": "상담 시간 취소 (예약 있으면 force+사유)",
    "submit": "익명 제출", "search": "건의 목록", "stats": "건의 통계", "set_status": "건의 상태 변경",
    "staff_list": "설문 목록 (응답 수 포함)", "create": "설문 생성 (초안)", "get_one": "설문 상세", "update": "설문 수정 (게시 후 문항 잠금)",
    "publish": "설문 게시", "close": "설문 종료", "duplicate": "설문 복제 (새 버전)", "delete": "초안 삭제",
    "results": "설문 결과 (최소 응답 수 미만이면 숨김)", "export": "엑셀 다운로드 (수식 주입 방어)",
    "student_list": "학생용 설문 목록 (본인 참여 여부)", "student_get": "학생용 설문 상세",
    "me": "현재 사용자·권한·CSRF 토큰", "logout": "로그아웃", "google_login": "Google 로그인 시작",
    "google_callback": "Google 로그인 콜백", "dev_login": "개발용 로그인 (운영 불가)", "healthz": "상태 확인",
}


def perm_of(dependant) -> str:
    for d in dependant.dependencies:
        p = getattr(d.call, "required_permission", None)
        if p is not None:
            return getattr(p, "value", p)
        inner = perm_of(d)
        if inner:
            return inner
    return ""


def main() -> None:
    app = create_app(Settings(env="test", database_url="sqlite://", dev_login_enabled=True))
    routes = []
    for r in app.routes:
        sub = getattr(r, "original_router", None)
        for route in (sub.routes if sub else [r]):
            if isinstance(route, APIRoute):
                routes.append(route)
    lines = ["# API 명세", "", "> `scripts/gen_api_doc.py`로 코드에서 자동 생성. 상세 스키마는 `docs/openapi.json` 또는 개발 서버 `/docs`.",
             "", "모든 변경 요청(POST/PUT/PATCH/DELETE)에는 `X-CSRF-Token` 헤더가 필요합니다 (`GET /api/me`의 `csrf_token`).",
             "오류 응답 형식: `{\"error\": \"코드\", \"message\": \"설명\"}`", "",
             "| 메서드 | 경로 | 필요 권한 | 설명 |", "|---|---|---|---|"]
    for route in sorted(routes, key=lambda x: (x.path, sorted(x.methods)[0])):
        doc = (route.endpoint.__doc__ or "").strip().splitlines()
        perm = perm_of(route.dependant) or ("공개" if route.path.startswith("/api") else "-")
        for m in sorted(route.methods - {"HEAD"}):
            lines.append(f"| {m} | `{route.path}` | {perm} | {KO.get(route.name) or (doc[0] if doc else route.name)} |")
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs/api.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "docs/openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(routes)} routes")


if __name__ == "__main__":
    main()
