"""설문 모델.

익명성 설계 원칙:
- participations: (survey_id, user_id)만 저장. 시각 없음 → 중복 참여 방지 용도.
- responses/answers: user_id 없음, 시각 없음, 순차 ID 대신 UUID.
- 두 테이블을 잇는 외래키나 공통 값이 없다.
한계는 docs/anonymity.md 참고 (DB 물리 저장 순서, 소수 응답 등).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime, utcnow

QUESTION_TYPES = ("short", "long", "single", "multi", "dropdown", "scale5")
CHOICE_TYPES = ("single", "multi", "dropdown")


class Survey(Base):
    __tablename__ = "surveys"
    __table_args__ = (
        CheckConstraint("status IN ('draft','published','closed')", name="ck_surveys_status"),
        CheckConstraint("min_results >= 1", name="ck_surveys_min_results"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    course_name: Mapped[str] = mapped_column(String(120), default="")
    semester: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    opens_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closes_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # 응답 수가 이 값 미만이면 결과를 공개하지 않는다 (소수 응답 재식별 방지)
    min_results: Mapped[int] = mapped_column(Integer, default=5)
    source_survey_id: Mapped[int | None] = mapped_column(ForeignKey("surveys.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    questions: Mapped[list["Question"]] = relationship(
        order_by="Question.position", cascade="all, delete-orphan", lazy="selectin"
    )


class Question(Base):
    __tablename__ = "survey_questions"
    __table_args__ = (
        CheckConstraint(
            "qtype IN ('short','long','single','multi','dropdown','scale5')", name="ck_q_type"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    qtype: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(500))
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    options: Mapped[list] = mapped_column(JSON, default=list)


class Participation(Base):
    __tablename__ = "survey_participations"

    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)


class Response(Base):
    __tablename__ = "survey_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id", ondelete="CASCADE"), index=True)


class Answer(Base):
    __tablename__ = "survey_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    response_id: Mapped[str] = mapped_column(
        ForeignKey("survey_responses.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("survey_questions.id", ondelete="CASCADE"), index=True)
    value: Mapped[object] = mapped_column(JSON)
