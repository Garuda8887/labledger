"""Cross-check tests (BRIEF §5.5)."""
from __future__ import annotations

from app.catalog.crosschecks import run_crosschecks


def test_lipid_sum_ok():
    f = run_crosschecks(
        {"total_cholesterol": 200, "hdl": 50, "ldl": 120, "vldl": 30}
    )
    assert not any(x.code == "lipid_sum_mismatch" for x in f)


def test_lipid_sum_bad():
    f = run_crosschecks(
        {"total_cholesterol": 300, "hdl": 50, "ldl": 100, "vldl": 20}
    )
    assert any(x.code == "lipid_sum_mismatch" for x in f)


def test_mch_formula():
    # Hb 15, RBC 5 → MCH 30
    f = run_crosschecks({"hemoglobin": 15.0, "rbc": 5.0, "mch": 30.0})
    assert not any(x.code == "mch_formula_mismatch" for x in f)
    f2 = run_crosschecks({"hemoglobin": 15.0, "rbc": 5.0, "mch": 22.0})
    assert any(x.code == "mch_formula_mismatch" for x in f2)


def test_bili_sum():
    f = run_crosschecks(
        {"bilirubin_total": 1.0, "bilirubin_direct": 0.3, "bilirubin_indirect": 0.7}
    )
    assert not any(x.code == "bilirubin_sum_mismatch" for x in f)


def test_ag_ratio():
    f = run_crosschecks({"albumin": 4.0, "globulin": 2.0, "ag_ratio": 2.0})
    assert not any(x.code == "ag_ratio_mismatch" for x in f)


def test_tc_hdl():
    f = run_crosschecks({"total_cholesterol": 200, "hdl": 50, "tc_hdl_ratio": 4.0})
    assert not any(x.code == "tc_hdl_ratio_mismatch" for x in f)


def test_differential_sum():
    f = run_crosschecks(
        {
            "neutrophils_pct": 60,
            "lymphocytes_pct": 30,
            "monocytes_pct": 5,
            "eosinophils_pct": 3,
            "basophils_pct": 2,
        }
    )
    assert not any(x.code == "differential_pct_sum" for x in f)
    f2 = run_crosschecks(
        {
            "neutrophils_pct": 60,
            "lymphocytes_pct": 30,
            "monocytes_pct": 5,
            "eosinophils_pct": 3,
            "basophils_pct": 20,
        }
    )
    assert any(x.code == "differential_pct_sum" for x in f2)
