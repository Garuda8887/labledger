"""Regression: Flag/Method/multi-column layouts + confidence caps."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.extraction.digital import extract_digital_pdf
from app.extraction.layout import parse_pages, _unit_known, ColumnMap
from app.extraction.types import PageContent, WordBox

SYNTH = Path(__file__).resolve().parents[1] / "fixtures" / "synth" / "digital"

# Worst layouts from the 45% baseline eval (unit column collapse / multi-col).
HARD_LAYOUTS = (
    "thornfield_flags",
    "willowgate_method",
    "riverstone_multicol",
    "northfen_dense",
    "duskvale_sex_ranges",
    "stonequill_comparators",
    "brightmarsh_multipage",
)


@pytest.mark.parametrize("layout_id", HARD_LAYOUTS)
def test_hard_layout_keeps_unit_column(layout_id: str):
    pdf = SYNTH / f"{layout_id}.pdf"
    assert pdf.exists(), pdf
    pages = extract_digital_pdf(pdf)
    rows = parse_pages(pages)
    # Core CBC markers must keep a recognized unit (not ref/method text).
    by_name = {r.raw_test_name.lower(): r for r in rows}
    hb = next((r for n, r in by_name.items() if "hemoglobin" in n), None)
    assert hb is not None, f"{layout_id}: missing Hemoglobin"
    assert hb.value_numeric is not None
    assert hb.raw_unit and _unit_known(hb.raw_unit), (
        f"{layout_id}: unit stolen/missing → {hb.raw_unit!r}"
    )
    assert " " not in (hb.raw_unit or ""), f"unit should be single token: {hb.raw_unit!r}"


def test_riverstone_splits_side_by_side_tables():
    pages = extract_digital_pdf(SYNTH / "riverstone_multicol.pdf")
    rows = parse_pages(pages)
    names = {r.raw_test_name.lower() for r in rows}
    assert any("hemoglobin" in n for n in names)
    assert any("neutrophil" in n for n in names)
    assert all("multi_table_page" in (r.confidence_reasons or []) for r in rows if r.value_numeric)


def test_missing_unit_forces_low_confidence():
    """Numeric row without a unit must never be high-confidence."""
    page = PageContent(
        page_number=1,
        kind="digital",
        width=600,
        height=800,
        words=[
            WordBox("Test", 40, 100, 60, 112, 1.0),
            WordBox("Result", 200, 100, 230, 112, 1.0),
            WordBox("Unit", 300, 100, 320, 112, 1.0),
            WordBox("Range", 400, 100, 430, 112, 1.0),
            WordBox("Hemoglobin", 40, 120, 100, 132, 1.0),
            WordBox("14.2", 200, 120, 220, 132, 1.0),
            # deliberately no unit word
            WordBox("13.0", 400, 120, 420, 132, 1.0),
            WordBox("-", 422, 120, 428, 132, 1.0),
            WordBox("17.0", 430, 120, 450, 132, 1.0),
        ],
    )
    rows = parse_pages([page])
    hb = next(r for r in rows if "hemoglobin" in r.raw_test_name.lower())
    assert hb.raw_unit is None or not _unit_known(hb.raw_unit or "")
    assert hb.confidence < 0.85
    assert "missing_unit" in hb.confidence_reasons


def test_columnmap_left_edge_keeps_flag_from_stealing_unit():
    """Flag between Result and Unit must not claim Unit cells (nearest-centre bug)."""
    cmap = ColumnMap(test=40, result=200, flag=280, unit=320, ref=400)
    # Word sitting in the Unit column (left edge past Unit header).
    assert cmap.role_at(326, 600) == "unit"
    assert cmap.role_at(290, 600) == "flag"
    assert cmap.role_at(210, 600) == "result"


def test_ocr_source_caps_confidence():
    page = PageContent(
        page_number=1,
        kind="scanned",
        width=600,
        height=800,
        words=[
            WordBox("Test", 40, 100, 60, 112, 0.95),
            WordBox("Result", 200, 100, 230, 112, 0.95),
            WordBox("Unit", 300, 100, 320, 112, 0.95),
            WordBox("Range", 400, 100, 430, 112, 0.9),
            WordBox("Hemoglobin", 40, 120, 100, 132, 0.7),
            WordBox("14.2", 200, 120, 220, 132, 0.65),
            WordBox("g/dL", 300, 120, 330, 132, 0.7),
            WordBox("13.0", 400, 120, 420, 132, 0.7),
            WordBox("-", 422, 120, 428, 132, 0.7),
            WordBox("17.0", 430, 120, 450, 132, 0.7),
        ],
    )
    rows = parse_pages([page])
    hb = next(r for r in rows if "hemoglobin" in r.raw_test_name.lower())
    assert hb.confidence < 0.85
    assert "ocr_source" in hb.confidence_reasons
