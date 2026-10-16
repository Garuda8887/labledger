from __future__ import annotations

from pathlib import Path

from app.extraction.classify import classify_pdf, classify_source
from app.extraction.digital import extract_digital_pdf
from app.extraction.layout import parse_pages, _parse_value
from app.extraction.metadata import extract_metadata

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "extraction"


def test_classify_digital_pdf():
    kinds = classify_pdf(FIXTURES / "northvale_cbc_lipid.pdf")
    assert kinds == ["digital"]
    source, kinds2 = classify_source(FIXTURES / "northvale_cbc_lipid.pdf", "application/pdf")
    assert source == "digital_pdf"
    assert kinds2 == ["digital"]


def test_parse_value_comparators_and_qualitative():
    comp, raw, num, qual, _ = _parse_value("<0.01")
    assert comp == "<"
    assert num == 0.01
    assert qual is None
    _, _, num2, qual2, _ = _parse_value("Non-reactive")
    assert num2 is None
    assert qual2 is not None


def test_layout_northvale_extracts_hemoglobin():
    pages = extract_digital_pdf(FIXTURES / "northvale_cbc_lipid.pdf")
    rows = parse_pages(pages)
    names = [r.raw_test_name.lower() for r in rows]
    assert any("hemoglobin" in n for n in names)
    hb = next(r for r in rows if "hemoglobin" in r.raw_test_name.lower())
    assert hb.value_numeric == 13.8
    assert hb.raw_unit and "g" in hb.raw_unit.lower()
    # TSH comparator
    tsh = next((r for r in rows if "tsh" in r.raw_test_name.lower()), None)
    assert tsh is not None
    assert tsh.comparator == "<"
    assert tsh.value_numeric == 0.01


def test_layout_cedarbrook_qualitative_and_alt_headers():
    pages = extract_digital_pdf(FIXTURES / "cedarbrook_liver_vit.pdf")
    rows = parse_pages(pages)
    assert len(rows) >= 4
    hbs = next((r for r in rows if "hbsag" in r.raw_test_name.lower()), None)
    assert hbs is not None
    assert hbs.value_qualitative is not None or "reactive" in hbs.raw_value.lower()


def test_metadata_northvale():
    pages = extract_digital_pdf(FIXTURES / "northvale_cbc_lipid.pdf")
    meta = extract_metadata(pages)
    assert meta.lab_name and "Northvale" in meta.lab_name
    assert meta.sample_id and "NV-2026" in meta.sample_id
    assert meta.report_date == "2026-03-15"
    assert meta.printed_patient_name and "Alex" in meta.printed_patient_name
    assert meta.printed_patient_sex == "male"
