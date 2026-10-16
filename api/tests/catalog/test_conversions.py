"""Every conversion factor + round-trips + property-style tests (BRIEF §5.4)."""
from __future__ import annotations

import math
import random

import pytest

from app.catalog.conversions import (
    ConversionUnsupported,
    all_verified_factors,
    convert,
    convert_bun_urea,
    convert_to_canonical,
    load_conversion_table,
)


# Explicit BRIEF §5.4 expectations (insulin uses verified 6.0, not outdated 6.945)
BRIEF_FACTORS = [
    ("glucose", "mg/dL", "mmol/L", 0.0555, None),
    ("cholesterol", "mg/dL", "mmol/L", 0.02586, None),
    ("triglycerides", "mg/dL", "mmol/L", 0.01129, None),
    ("creatinine", "mg/dL", "µmol/L", 88.4, None),
    ("uric_acid", "mg/dL", "µmol/L", 59.48, None),
    ("bilirubin", "mg/dL", "µmol/L", 17.1, None),
    ("calcium", "mg/dL", "mmol/L", 0.2495, None),
    ("hemoglobin", "g/dL", "g/L", 10.0, None),
    ("vitamin_d", "ng/mL", "nmol/L", 2.496, None),
    ("vitamin_b12", "pg/mL", "pmol/L", 0.738, None),
    ("testosterone", "ng/dL", "nmol/L", 0.0347, None),
    ("t4", "µg/dL", "nmol/L", 12.87, None),
    ("cortisol", "µg/dL", "nmol/L", 27.59, None),
    ("insulin", "µIU/mL", "pmol/L", 6.0, None),
    ("iron", "µg/dL", "µmol/L", 0.179, None),
]


def test_all_seed_factors_verified():
    table = load_conversion_table()
    assert len(table) >= 15
    for c in table:
        assert c.verified, f"{c.analyte_group} not verified"


@pytest.mark.parametrize("group,fu,tu,factor,formula", BRIEF_FACTORS)
def test_each_brief_factor(group, fu, tu, factor, formula):
    matches = [c for c in all_verified_factors() if c.analyte_group == group]
    assert matches, f"missing group {group}"
    c = matches[0]
    assert c.from_unit == fu
    assert c.to_unit == tu
    assert c.factor == pytest.approx(factor)
    # Spot-check apply
    if c.formula:
        assert c.apply(6.5) == pytest.approx((6.5 - 2.15) * 10.929)
    else:
        assert c.apply(100.0) == pytest.approx(100.0 * factor + c.offset)


def test_hba1c_formula():
    c = [x for x in all_verified_factors() if x.analyte_group == "hba1c_ngsp_ifcc"][0]
    # 6.5% → ~47.54 mmol/mol
    assert c.apply(6.5) == pytest.approx((6.5 - 2.15) * 10.929)
    assert c.apply_reverse(c.apply(6.5)) == pytest.approx(6.5)


@pytest.mark.parametrize("group,fu,tu,factor,formula", BRIEF_FACTORS)
def test_round_trip(group, fu, tu, factor, formula):
    c = [x for x in all_verified_factors() if x.analyte_group == group][0]
    for v in (1.0, 10.0, 42.5, 100.0, 200.0):
        out = c.apply(v)
        back = c.apply_reverse(out)
        assert back == pytest.approx(v, rel=1e-9, abs=1e-9)


def test_bun_urea():
    assert convert_bun_urea(10.0, from_analyte="bun") == pytest.approx(21.4)
    assert convert_bun_urea(21.4, from_analyte="urea") == pytest.approx(10.0)


def test_lakhs_cumm_platelets():
    # 2.5 Lakhs/cumm = 250,000 /µL = 250 ×10^3/µL
    assert convert(2.5, "Lakhs/cumm", "/µL") == pytest.approx(250_000.0)
    assert convert(2.5, "Lakhs/cumm", "10^3/µL") == pytest.approx(250.0)


def test_identity_uiu_miu():
    assert convert(3.2, "µIU/mL", "mIU/L") == pytest.approx(3.2)


def test_convert_to_canonical_unrecognized():
    nv, err, reasons = convert_to_canonical(100, "frobnitz", "mg/dL")
    assert nv is None
    assert err == "unit_unrecognized"
    assert "unit_unrecognized" in reasons


def test_convert_glucose_via_api():
    assert convert(180, "mg/dL", "mmol/L", biomarker_key="glucose_fasting") == pytest.approx(
        180 * 0.0555
    )


def test_unsupported_pair():
    with pytest.raises(ConversionUnsupported):
        convert(1.0, "mg/dL", "kg/L", biomarker_key="glucose_fasting")


def test_property_roundtrip_random():
    """Property-style: random values round-trip for every factor."""
    rng = random.Random(42)
    for c in all_verified_factors():
        for _ in range(20):
            v = rng.uniform(0.5, 500.0)
            back = c.apply_reverse(c.apply(v))
            assert math.isclose(back, v, rel_tol=1e-9, abs_tol=1e-9), c.analyte_group


def test_property_monotonic_positive_factors():
    """For positive factors without special formula, convert preserves order."""
    for c in all_verified_factors():
        if c.formula:
            continue
        if c.factor <= 0:
            continue
        assert c.apply(10) < c.apply(20)
