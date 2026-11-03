"""엑셀 내보내기. 수식 주입(CSV/Formula Injection) 방어 포함."""
from __future__ import annotations

from io import BytesIO
from typing import Iterable, Sequence

from openpyxl import Workbook
from openpyxl.styles import Font

DANGEROUS_PREFIX = ("=", "+", "-", "@", "\t", "\r", "\n")


def sanitize_cell(value: object) -> object:
    if isinstance(value, str):
        stripped = value.lstrip()
        if value.startswith(DANGEROUS_PREFIX) or stripped.startswith(DANGEROUS_PREFIX):
            return "'" + value
    return value


def build_workbook(sheets: Sequence[tuple[str, Sequence[str], Iterable[Sequence[object]]]]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for title, header, rows in sheets:
        ws = wb.create_sheet(title=title[:31])
        ws.append([sanitize_cell(h) for h in header])
        for row in rows:
            ws.append([sanitize_cell(v) for v in row])
        for cell in ws[1]:
            cell.font = Font(bold=True)
    # 문자열이 수식으로 해석되지 않도록 data_type 고정
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
