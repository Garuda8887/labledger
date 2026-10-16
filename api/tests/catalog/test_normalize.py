"""End-to-end normalize() on sample rows."""
from __future__ import annotations

from app.catalog.seed_loader import build_normalize_context
from app.catalog.normalize import normalize_row, normalize_rows
from app.catalog.flags import check_plausibility


def test_normalize_sgpt_high():
    ctx = build_normalize_context()
    ctx.profile_sex = "male"
    out = normalize_row(
        {
            "raw_test_name": "SGPT",
            "raw_value": "85",
            "raw_unit": "U/L",
            "raw_ref_text": "Up to 40",
            "confidence": 0.9,
        },
        ctx,
        printed_flag="H",
    )
    assert out["biomarker_key"] == "alt"
    assert out["normalized_value"] == 85.0
    assert out["canonical_unit"] == "U/L"
    assert out["flag"] == "high"
    assert out["ref_high"] == 40.0
    assert out["ref_source"] == "report"
    assert out["confidence"] >= 0.5


def test_normalize_gms_percent_hb():
    ctx = build_normalize_context()
    ctx.profile_sex = "male"
    out = normalize_row(
        {
            "raw_test_name": "Hb",
            "raw_value": "14.2",
            "raw_unit": "Gms%",
            "raw_ref_text": "Male: 13.0 - 17.0 / Female: 12.0 - 15.0",
        },
        ctx,
    )
    assert out["biomarker_key"] == "hemoglobin"
    assert out["normalized_value"] == 14.2
    assert out["canonical_unit"] == "g/dL"
    assert out["flag"] == "normal"
    assert out["ref_low"] == 13.0


def test_normalize_unit_unrecognized():
    ctx = build_normalize_context()
    out = normalize_row(
        {
            "raw_test_name": "Glucose Fasting",
            "raw_value": "100",
            "raw_unit": "scoops",
            "raw_ref_text": "70 - 99",
        },
        ctx,
    )
    assert "unit_unrecognized" in out["confidence_reasons"]
    assert out["normalized_value"] is None
    assert out["confidence"] <= 0.4


def test_normalize_lakhs_platelets():
    ctx = build_normalize_context()
    out = normalize_row(
        {
            "raw_test_name": "Platelet Count",
            "raw_value": "2.5",
            "raw_unit": "Lakhs/cumm",
            "raw_ref_text": "1.5 - 4.5",
        },
        ctx,
    )
    assert out["biomarker_key"] == "platelets"
    assert out["normalized_value"] == 250.0  # 10^3/µL
    assert out["canonical_unit"] == "10^3/µL"


def test_plausibility_suspect():
    assert check_plausibility(500.0, 2.0, 25.0) == "suspect_unit_or_misread"
    assert check_plausibility(14.0, 2.0, 25.0) is None


def test_normalize_rows_crosscheck():
    ctx = build_normalize_context()
    rows = [
        {"raw_test_name": "Cholesterol", "raw_value": "300", "raw_unit": "mg/dL"},
        {"raw_test_name": "HDL", "raw_value": "50", "raw_unit": "mg/dL"},
        {"raw_test_name": "LDL", "raw_value": "100", "raw_unit": "mg/dL"},
        {"raw_test_name": "VLDL", "raw_value": "20", "raw_unit": "mg/dL"},
    ]
    out = normalize_rows(rows, ctx)
    assert any(
        any("lipid_sum_mismatch" in r for r in row["confidence_reasons"]) for row in out
    )


def test_unmatched():
    ctx = build_normalize_context()
    out = normalize_row(
        {"raw_test_name": "Quantum Flux Capacitance", "raw_value": "1", "raw_unit": "U/L"},
        ctx,
    )
    assert out["biomarker_key"] is None
    assert out["match_method"] == "unmatched"


def test_ocr_reasons_block_exact_alias_boost():
    """Extractor OCR / missing-unit caps must survive exact_alias normalize."""
    ctx = build_normalize_context()
    out = normalize_row(
        {
            "raw_test_name": "Hemoglobin",
            "raw_value": "14.2",
            "raw_unit": "g/dL",
            "confidence": 0.7,
            "confidence_reasons": ["ocr_source", "ocr_low_word_conf"],
        },
        ctx,
    )
    assert out["match_method"] == "exact_alias"
    assert out["confidence"] < 0.85


def test_missing_unit_stays_below_high_conf_gate():
    ctx = build_normalize_context()
    out = normalize_row(
        {
            "raw_test_name": "Hemoglobin",
            "raw_value": "14.2",
            "raw_unit": None,
            "confidence": 0.6,
            "confidence_reasons": ["missing_unit"],
        },
        ctx,
    )
    assert out["confidence"] < 0.85
