"""Unit string normalization tests (BRIEF §5.3)."""
from __future__ import annotations

import pytest

from app.catalog.units import normalize_unit, units_are_identity_equivalent


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("mg/dl", "mg/dL"),
        ("MG/DL", "mg/dL"),
        ("mg / dL", "mg/dL"),
        ("gm/dL", "g/dL"),
        ("Gms%", "g/dL"),
        ("g%", "g/dL"),
        ("g/%", "g/dL"),
        ("µIU/mL", "µIU/mL"),
        ("μIU/mL", "µIU/mL"),  # Greek mu
        ("uIU/mL", "µIU/mL"),
        ("mIU/L", "mIU/L"),
        ("/cumm", "/µL"),
        ("/cu.mm", "/µL"),
        ("cells/µL", "/µL"),
        ("thou/mm3", "10^3/µL"),
        ("10^3/µL", "10^3/µL"),
        ("×10⁹/L", "10^9/L"),
        ("x10^9/L", "10^9/L"),
        ("Lakhs/cumm", "Lakhs/cumm"),
        ("lacs/cumm", "Lakhs/cumm"),
        ("mill/cumm", "10^6/µL"),
        ("10^6/µL", "10^6/µL"),
        ("10^12/L", "10^12/L"),
        ("U/L", "U/L"),
        ("IU/L", "IU/L"),
        ("ng/mL", "ng/mL"),
        ("pg/mL", "pg/mL"),
        ("%", "%"),
        ("10³/µL", "10^3/µL"),
        ("µg/dL", "µg/dL"),
        ("mcg/dL", "µg/dL"),
    ],
)
def test_normalize_known_units(raw, expected):
    assert normalize_unit(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["frobnitz", "widgets/L", "kg/m^2", "", None, "???"] ,
)
def test_unknown_unit_no_guess(raw):
    assert normalize_unit(raw) is None


def test_identity_equivalents():
    assert units_are_identity_equivalent("µIU/mL", "mIU/L")
    assert units_are_identity_equivalent("ng/mL", "µg/L")
    assert units_are_identity_equivalent("10^3/µL", "10^9/L")
    assert units_are_identity_equivalent("10^6/µL", "10^12/L")
    assert not units_are_identity_equivalent("mg/dL", "mmol/L")
