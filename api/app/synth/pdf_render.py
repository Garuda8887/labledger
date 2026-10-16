"""Render fictional lab report PDFs with reportlab. Layout-driven, no real brands."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.synth.layouts import METHOD_BY_KEY, LayoutSpec
from app.synth.panels import TruthRow


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "LabTitle",
            parent=base["Heading1"],
            fontSize=14,
            spaceAfter=2,
            textColor=colors.HexColor("#1a1a2e"),
        ),
        "sub": ParagraphStyle(
            "LabSub",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#444"),
            spaceAfter=1,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontSize=9,
            textColor=colors.HexColor("#0f3460"),
            spaceBefore=8,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["Normal"],
            fontSize=7.5,
            leading=9,
        ),
        "cell_wrap": ParagraphStyle(
            "CellWrap",
            parent=base["Normal"],
            fontSize=6.5,
            leading=8,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=6.5,
            textColor=colors.HexColor("#666"),
        ),
    }


def _cell(text: str, style, wrap: bool = False) -> Paragraph:
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = safe.replace("\n", "<br/>")
    return Paragraph(safe, style["cell_wrap"] if wrap else style["cell"])


def _row_cells(
    row: TruthRow,
    layout: LayoutSpec,
    styles,
) -> list:
    cells = []
    for col in layout.columns:
        if col == "test":
            cells.append(_cell(row.raw_test_name, styles))
        elif col == "result":
            cells.append(_cell(row.raw_value, styles))
        elif col == "unit":
            cells.append(_cell(row.raw_unit or "", styles))
        elif col == "ref":
            ref = row.raw_ref_text or ""
            if layout.wrap_refs and "\n" not in ref and len(ref) > 28:
                # Force wrap for long single-line refs
                mid = len(ref) // 2
                ref = ref[:mid] + "\n" + ref[mid:]
            cells.append(_cell(ref, styles, wrap=layout.wrap_refs or ("\n" in ref)))
        elif col == "flag":
            cells.append(_cell(row.printed_flag or "", styles))
        elif col == "method":
            cells.append(_cell(METHOD_BY_KEY.get(row.biomarker_key, "Automated"), styles))
        else:
            cells.append(_cell("", styles))
    return cells


def _col_widths(layout: LayoutSpec, usable: float) -> list[float]:
    n = len(layout.columns)
    # Weight by column type
    weights = {
        "test": 2.4,
        "result": 1.0,
        "unit": 1.0,
        "ref": 2.2,
        "flag": 0.5,
        "method": 1.4,
    }
    wsum = sum(weights.get(c, 1.0) for c in layout.columns)
    return [usable * weights.get(c, 1.0) / wsum for c in layout.columns]


def _header_row(layout: LayoutSpec, styles) -> list:
    return [_cell(layout.header_labels.get(c, c.upper()), styles) for c in layout.columns]


def _table_style(has_header: bool = True) -> TableStyle:
    cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold") if has_header else ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")) if has_header else ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b0b8c4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    return TableStyle([c for c in cmds if c])


def render_report_pdf(
    layout: LayoutSpec,
    rows: Sequence[TruthRow],
    *,
    patient_name: str = "Aarav Mehta",
    patient_age: str = "42 Y",
    patient_sex: str = "Male",
    report_date: date | None = None,
    sample_id: str = "SYN-0001",
    out_path: Path | None = None,
) -> bytes:
    """Build a digital PDF for one layout + ground-truth rows. Returns PDF bytes."""
    report_date = report_date or date(2024, 6, 15)
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"{layout.lab_name} — synthetic",
        author="Labledger Synth (fictional)",
    )
    usable = A4[0] - 28 * mm
    story: list = []

    # Header
    story.append(Paragraph(layout.lab_name, styles["title"]))
    story.append(Paragraph("Fictional laboratory report — for software evaluation only", styles["sub"]))
    if layout.clutter:
        for line in layout.header_extra:
            story.append(Paragraph(line, styles["sub"]))
    story.append(Spacer(1, 4 * mm))

    meta_data = [
        [
            _cell(f"Patient: {patient_name}", styles),
            _cell(f"Age/Sex: {patient_age} / {patient_sex}", styles),
        ],
        [
            _cell(f"Sample ID: {sample_id}", styles),
            _cell(f"Report Date: {report_date.strftime('%d/%m/%Y')}", styles),
        ],
        [
            _cell(f"Collected: {report_date.strftime('%d-%b-%Y')}", styles),
            _cell("Status: Final (synthetic)", styles),
        ],
    ]
    meta = Table(meta_data, colWidths=[usable / 2, usable / 2])
    meta.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#8899aa")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f9fc")),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 4 * mm))

    # Group rows by section
    sections: list[tuple[str | None, list[TruthRow]]] = []
    current_sec: str | None = None
    bucket: list[TruthRow] = []
    for r in rows:
        sec = r.section if layout.section_headers else None
        if sec != current_sec and bucket:
            sections.append((current_sec, bucket))
            bucket = []
        current_sec = sec
        bucket.append(r)
    if bucket:
        sections.append((current_sec, bucket))

    widths = _col_widths(layout, usable if not layout.multi_column else usable / 2 - 2 * mm)

    def emit_section(sec_name: str | None, sec_rows: list[TruthRow], col_w: list[float]) -> list:
        parts: list = []
        if sec_name and layout.section_headers:
            parts.append(Paragraph(sec_name, styles["section"]))
        data = [_header_row(layout, styles)]
        for r in sec_rows:
            data.append(_row_cells(r, layout, styles))
        t = Table(data, colWidths=col_w, repeatRows=1)
        t.setStyle(_table_style(True))
        parts.append(t)
        parts.append(Spacer(1, 2 * mm))
        return parts

    if layout.multi_column and len(sections) >= 2:
        # Pair sections side by side where possible
        i = 0
        while i < len(sections):
            left_sec, left_rows = sections[i]
            left_bits = emit_section(left_sec, left_rows, widths)
            if i + 1 < len(sections):
                right_sec, right_rows = sections[i + 1]
                right_bits = emit_section(right_sec, right_rows, widths)
                # Wrap each side in a nested flowable via KeepTogether lists → use inner tables only
                left_table = left_bits[1] if len(left_bits) > 1 else left_bits[0]
                right_table = right_bits[1] if len(right_bits) > 1 else right_bits[0]
                if left_sec:
                    story.append(Paragraph(f"{left_sec}  |  {right_sec or ''}", styles["section"]))
                pair = Table([[left_table, right_table]], colWidths=[usable / 2, usable / 2])
                pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story.append(pair)
                i += 2
            else:
                for p in left_bits:
                    story.append(p)
                i += 1
            if layout.multi_page and left_sec in layout.page_break_after_sections:
                story.append(PageBreak())
                story.append(Paragraph(f"{layout.lab_name} (cont.)", styles["sub"]))
    else:
        for sec_name, sec_rows in sections:
            block = emit_section(sec_name, sec_rows, _col_widths(layout, usable))
            story.append(KeepTogether(block))
            if layout.multi_page and sec_name in layout.page_break_after_sections:
                story.append(PageBreak())
                story.append(Paragraph(f"{layout.lab_name} — continued", styles["title"]))
                story.append(Paragraph(f"Sample {sample_id} · {patient_name}", styles["sub"]))

    story.append(Spacer(1, 6 * mm))
    for line in layout.footer_lines or ["*** End of synthetic report ***"]:
        story.append(Paragraph(line.replace("{page}", "auto"), styles["footer"]))
    if layout.clutter:
        story.append(Paragraph("Barcode: ||||| SYNTH |||||  ·  QR placeholder  ·  Stamp: VERIFIED", styles["footer"]))

    doc.build(story)
    pdf = buf.getvalue()
    if out_path is not None:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(pdf)
    return pdf
