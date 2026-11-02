"""개발용 가상 데이터 생성 (실제 학생 데이터 사용 금지).

실행: APP_ENV=development DATABASE_URL=sqlite:///./classbridge_dev.db python scripts/seed_demo.py
운영 환경(APP_ENV=production)에서는 실행을 거부한다.
"""
from __future__ import annotations

import sys
from datetime import time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import load_settings  # noqa: E402
from app.core.identity import VerifiedIdentity  # noqa: E402
from app.db import make_engine, make_sessionmaker, utcnow  # noqa: E402
from app.services import booking_service, survey_service, user_service  # noqa: E402
from app.services.survey_service import QuestionInput  # noqa: E402
from app.timeutil import today_kst  # noqa: E402


def main() -> None:
    s = load_settings()
    if s.is_production:
        sys.exit("운영 환경에서는 가상 데이터를 만들 수 없습니다")
    db = make_sessionmaker(make_engine(s.database_url))()

    def user(email, name):
        return user_service.login_or_register(db, s, VerifiedIdentity(f"dev:{email}", email, True, name))

    prof = user((s.professor_emails or ["prof@test.ac.kr"])[0], "김교수")
    user((s.admin_emails or ["admin@test.ac.kr"])[0], "관리자")
    students = [user(f"student{i}@test.ac.kr", f"가상학생{i}") for i in range(1, 6)]
    start = today_kst(utcnow()) + timedelta(days=1)
    booking_service.create_slots(db, prof, booking_service.SlotSpec(
        start_date=start, start_time=time(10), end_time=time(12), duration_minutes=30, repeat_weeks=2,
        weekdays=[start.weekday(), (start.weekday() + 2) % 7], location="공학관 512호"))
    booking_service.create_slots(db, prof, booking_service.SlotSpec(
        start_date=start, start_time=time(15), end_time=time(16), duration_minutes=60, kind="group", capacity=4,
        location="세미나실"))
    sv = survey_service.create(db, prof, "중간 강의 설문 (예시)", "가상 데이터입니다.", [
        QuestionInput("scale5", "수업 전반 만족도", True),
        QuestionInput("single", "수업 난이도", True, ["쉬움", "적당함", "어려움"]),
        QuestionInput("long", "개선했으면 하는 점"),
    ], None, None, 3)
    survey_service.publish(db, prof, sv.id)
    print(f"완료: 학생 {len(students)}명, 상담 시간, 설문 1개 생성")


if __name__ == "__main__":
    main()
