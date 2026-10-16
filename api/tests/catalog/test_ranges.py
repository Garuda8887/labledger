"""Reference range parsing — all BRIEF §5.6 formats."""
from __future__ import annotations

import pytest

from app.catalog.ranges import compute_flag, parse_reference_range, printed_flag_mismatch


def test_interval_hyphen():
    r = parse_reference_range("13.0 - 17.0")
    assert r is not None
    assert r.low == 13.0 and r.high == 17.0


def test_interval_en_dash():
    r = parse_reference_range("13.0–17.0")
    assert r.low == 13.0 and r.high == 17.0


def test_less_than():
    r = parse_reference_range("< 200")
    assert r.low is None and r.high == 200.0


def test_up_to():
    r = parse_reference_range("Up to 40")
    assert r.high == 40.0 and r.low is None


def test_greater_than():
    r = parse_reference_range("> 30")
    assert r.low == 30.0 and r.high is None


def test_sex_specific_male():
    text = "Male: 13.0 - 17.0 / Female: 12.0 - 15.0"
    r = parse_reference_range(text, sex="male")
    assert r.sex_specific
    assert r.low == 13.0 and r.high == 17.0
    r2 = parse_reference_range(text, sex="female")
    assert r2.low == 12.0 and r2.high == 15.0


def test_multi_tier_desirable():
    text = "Desirable < 200, Borderline 200–239, High ≥ 240"
    r = parse_reference_range(text)
    assert r is not None
    assert r.tier == "desirable"
    assert r.high == 200.0
    assert r.low is None


def test_flag_normal_high_low():
    assert compute_flag(15.0, 13.0, 17.0) == "normal"
    assert compute_flag(18.0, 13.0, 17.0) == "high"
    assert compute_flag(10.0, 13.0, 17.0) == "low"
    assert compute_flag(150.0, None, 200.0) == "normal"
    assert compute_flag(250.0, None, 200.0) == "high"
    assert compute_flag(5.0, 30.0, None) == "low"
    assert compute_flag(None, 1.0, 2.0) == "unknown"
    assert compute_flag(1.0, None, None) == "unknown"


def test_printed_flag_mismatch():
    assert printed_flag_mismatch("high", "L") is not None
    assert printed_flag_mismatch("high", "H") is None
    assert printed_flag_mismatch("normal", None) is None
