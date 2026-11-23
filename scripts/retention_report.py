"""보관기간(최대 365일)이 지난 기록 수를 조회한다. 읽기 전용 — 아무것도 삭제하지 않는다.

실행: DATABASE_URL=... python scripts/retention_report.py [--json]
운영 DB에는 읽기 전용 계정(또는 DATABASE_URL_DIRECT) 사용을 권장한다.
결과는 건수·ID·가장 오래된 날짜만 출력하며 이름·이메일·본문은 출력하지 않는다.
삭제는 이 결과를 확인한 뒤 앱의 기존 삭제 기능 또는 별도 승인된 절차로 진행한다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.db import make_engine, make_sessionmaker, utcnow  # noqa: E402
from app.services.retention import overdue  # noqa: E402


def main() -> None:
    settings = load_settings()
    db = make_sessionmaker(make_engine(settings.database_url))()
    try:
        report = overdue(db, utcnow())
        db.rollback()  # read-only session: never commit
    finally:
        db.close()
    if "--json" in sys.argv:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"보관기간 {report['retention_days']}일 초과 기록 (기준 시각 {report['cutoff']})")
    for key, label in [("bookings", "예약·상담 기록"), ("suggestions", "건의"), ("surveys", "설문"),
                       ("support_tickets", "개발자 문의")]:
        item = report[key]
        extra = f" · 가장 오래된 기록 {item['oldest']}" if item.get("oldest") else ""
        ids = f" · 설문 ID {item['ids']}" if item.get("ids") else ""
        print(f"- {label}: {item['count']}건{extra}{ids} ({item['rule']})")
    print("이 스크립트는 삭제하지 않습니다. 삭제는 확인 후 별도로 진행하세요.")


if __name__ == "__main__":
    main()
