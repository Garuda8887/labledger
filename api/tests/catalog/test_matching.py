"""Alias matching tests."""
from __future__ import annotations

import json
from pathlib import Path

from app.catalog.matching import BiomarkerIndex, normalize_name

SEED = Path(__file__).resolve().parents[2] / "app" / "catalog" / "seed" / "biomarkers.json"


def _index():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    return BiomarkerIndex.from_biomarkers(data)


def test_exact_indian_aliases():
    idx = _index()
    for raw, key in [
        ("SGPT", "alt"),
        ("SGOT", "ast"),
        ("Hb", "hemoglobin"),
        ("PCV", "hematocrit"),
        ("TLC", "wbc"),
        ("FBS", "glucose_fasting"),
        ("PPBS", "glucose_pp"),
    ]:
        m = idx.match(raw)
        assert m.biomarker_key == key, (raw, m)
        assert m.method == "exact_alias"


def test_learned_alias():
    idx = _index()
    m = idx.match("My Custom Hb Name", learned_aliases={normalize_name("My Custom Hb Name"): "hemoglobin"})
    assert m.method == "learned_alias"
    assert m.biomarker_key == "hemoglobin"


def test_fuzzy_conservative():
    idx = _index()
    # Near miss should fuzzy if high enough
    m = idx.match("Hemoglobin")
    assert m.biomarker_key == "hemoglobin"
    # Garbage unmatched
    m2 = idx.match("Completely Unrelated Widget Level")
    assert m2.method == "unmatched"


def test_normalize_name():
    assert normalize_name("  SGPT (ALT)  ") == normalize_name("sgpt alt")
