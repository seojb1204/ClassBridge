from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

QType = Literal["short", "long", "single", "multi", "dropdown", "scale5"]


class QuestionIn(BaseModel):
    qtype: QType
    title: str = Field(max_length=500)
    required: bool = False
    options: list[str] = Field(default_factory=list, max_length=20)


class QuestionOut(QuestionIn):
    id: int
    position: int

    model_config = {"from_attributes": True}


class SurveyCreateIn(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=5000)
    course_name: str = Field(default="", max_length=120)
    semester: str = Field(default="", max_length=40)
    questions: list[QuestionIn] = Field(default_factory=list, max_length=50)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    min_results: int | None = Field(default=None, ge=1, le=50)


class SurveyUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    course_name: str | None = Field(default=None, max_length=120)
    semester: str | None = Field(default=None, max_length=40)
    questions: list[QuestionIn] | None = Field(default=None, max_length=50)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    min_results: int | None = Field(default=None, ge=1, le=50)


class SurveyOut(BaseModel):
    id: int
    title: str
    description: str
    course_name: str
    semester: str
    status: str
    opens_at: datetime | None
    closes_at: datetime | None
    min_results: int
    source_survey_id: int | None
    questions: list[QuestionOut]

    model_config = {"from_attributes": True}


class SurveyStaffListOut(BaseModel):
    id: int
    title: str
    course_name: str
    semester: str
    status: str
    opens_at: datetime | None
    closes_at: datetime | None
    response_count: int
    min_results: int


class SurveyStudentListOut(BaseModel):
    id: int
    title: str
    description: str
    course_name: str
    semester: str
    status: str
    closes_at: datetime | None
    is_open: bool
    participated: bool


class SurveyStudentOut(SurveyOut):
    participated: bool
    is_open: bool


class SubmitIn(BaseModel):
    # key = 문항 id(문자열), value = 응답
    answers: dict[str, str | int | list[str] | None]
