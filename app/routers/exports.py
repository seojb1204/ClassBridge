"""Authenticated downloads. Optional personal fields are excluded by default."""
import csv
from collections import Counter
from datetime import date
from html import escape
from io import StringIO
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import Principal, require
from app.core.errors import BadRequest, Forbidden
from app.core.permissions import P
from app.db import get_db
from app.infra.excel import build_workbook, sanitize_cell
from app.models import Booking, Slot, User
from app.services.booking_service import kst_range
from app.timeutil import to_kst as as_kst

router = APIRouter(prefix="/api/exports", tags=["exports"])
LABELS = {"booked": "예약 중", "completed": "상담 완료", "no_show": "미참석", "cancelled": "취소",
          "career": "진로", "employment": "취업", "academics": "학업", "campus": "학교생활", "other": "기타",
          "in_person": "대면", "online": "온라인"}


@router.get("/consultations")
def export_consultations(start: date, end: date, format: Literal["xlsx", "csv", "print"] = "xlsx",
                         student_id: int | None = None, include_numbers: bool = False,
                         include_contacts: bool = False, include_notes: bool = False,
                         p: Principal = Depends(require(P.SLOT_VIEW)), db: Session = Depends(get_db)):
    staff = p.can(P.BOOKING_MANAGE) and p.can(P.EXPORT)
    if not staff:
        if not p.can(P.BOOKING_SELF) or include_notes or (student_id is not None and student_id != p.user.id):
            raise Forbidden("본인 예약 정보만 내보낼 수 있습니다")
        student_id = p.user.id
    elif include_notes and not p.can(P.CONSULT_NOTE):
        raise Forbidden("상담 기록 내보내기 권한이 없습니다")
    days = (end - start).days + 1
    if days < 1 or days > 366:
        raise BadRequest("시작일과 종료일을 확인해 주세요. 한 번에 최대 366일입니다")
    since, until = kst_range(start, days)
    stmt = (select(Booking, User, Slot).join(User, User.id == Booking.student_id)
            .join(Slot, Slot.id == Booking.slot_id).where(Slot.start_at >= since, Slot.start_at < until))
    if student_id is not None:
        stmt = stmt.where(Booking.student_id == student_id)
    items = db.execute(stmt.order_by(Slot.start_at, Booking.id).limit(2001)).all()
    if len(items) > 2000:
        raise BadRequest("최대 2,000건까지 내보낼 수 있습니다. 기간 또는 학생을 좁혀 주세요")
    header = ["상담 시작", "상담 종료", "이름", "상담 유형", "상담 방식", "상태", "장소", "신청 주제"]
    if include_numbers:
        header += ["학번", "학년"]
    if include_contacts:
        header += ["이메일"]
    if include_notes:
        header += ["교수자 전용 상담 기록"]
    rows = []
    for b, u, slot in items:
        row = [as_kst(slot.start_at).strftime("%Y-%m-%d %H:%M"), as_kst(slot.end_at).strftime("%Y-%m-%d %H:%M"),
               b.applicant_name or u.name, LABELS.get(b.consultation_type, b.consultation_type),
               LABELS.get(b.consultation_mode, b.consultation_mode), LABELS[b.status], slot.location, b.topic]
        if include_numbers:
            row += [b.student_number, b.grade or ""]
        if include_contacts:
            row += [u.email]
        if include_notes:
            row += [b.professor_note]
        rows.append(row)
    filename = f"ClassBridge-{start}-{end}"
    counts = Counter(LABELS[b.status] for b, _, _ in items)
    if format == "xlsx":
        return Response(build_workbook([("상담 목록", header, rows), ("상태별 통계", ["상태", "건수"], counts.items())]),
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'})
    if format == "csv":
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        writer.writerows([[sanitize_cell(v) for v in row] for row in rows])
        return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'})
    sections = []
    for row in rows:
        values = "".join(f"<dt>{escape(key)}</dt><dd>{escape(str(value or '—'))}</dd>"
                         for key, value in zip(header, row, strict=True))
        sections.append(f'<section class="export-record"><dl>{values}</dl></section>')
    return HTMLResponse(f'''<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{filename}</title>
<link rel="stylesheet" href="/static/css/export.css"></head><body>
<div class="print-controls"><button id="print-export">PDF 저장 / 인쇄</button>
<p>인쇄 대상에서 ‘PDF로 저장’을 선택하세요. 내려받은 파일의 보관·공유에 주의해 주세요.</p></div>
<h1>ClassBridge 상담 자료</h1><p>{start} ~ {end} · {len(rows)}건 · 한국 시간 기준</p>
{''.join(sections) or '<p>해당 기간의 예약이 없습니다.</p>'}
<script src="/static/js/export-print.js"></script></body></html>''')
