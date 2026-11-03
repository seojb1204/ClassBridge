"""익명 건의. 작성자·제출 시각을 저장하지 않는다 (날짜만, 한국 기준)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

SUGGESTION_CATEGORIES = ("lecture", "assignment", "exam", "facility", "other")


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        CheckConstraint(
            "category IN ('lecture','assignment','exam','facility','other')", name="ck_sugg_category"
        ),
        CheckConstraint("status IN ('new','reviewed','archived')", name="ck_sugg_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    category: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    submitted_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="new")
