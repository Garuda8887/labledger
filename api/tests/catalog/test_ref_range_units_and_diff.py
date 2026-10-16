"""Regression: report ranges convert with the value; % differentials map to *_pct."""
import json
from pathlib import Path

from app.catalog.normalize import BiomarkerInfo, NormalizeContext, normalize_row
from app.catalog.matching import BiomarkerIndex

SEED = Path(__file__).resolve().parents[2] / "app" / "catalog" / "seed" / "biomarkers.json"


def _ctx():
    data = json.loads(SEED.read_text(encoding="utf8"))
    data = data if isinstance(data, list) else data["biomarkers"]
    infos = {}
    for i, b in enumerate(data):
        b = dict(b, id=f"id-{i}")
        infos[b["canonical_key"]] = BiomarkerInfo(
            id=b["id"],
            canonical_key=b["canonical_key"],
            display_name=b["display_name"],
            category=b["category"],
            canonical_unit=b["canonical_unit"],
            decimals=b.get("decimals", 1),
            aliases=b.get("aliases", []),
            plausibility_min=b.get("plausibility_min"),
            plausibility_max=b.get("plausibility_max"),
        )
    idx = BiomarkerIndex.from_biomarkers([dict(b, id=f"id-{i}") for i, b in enumerate(data)])
    return NormalizeContext(index=idx, biomarkers_by_key=infos, builtin_ranges=[], profile_sex="male")


def _row(name, value, unit, ref):
    return normalize_row(
        {"raw_test_name": name, "raw_value": value, "raw_unit": unit, "raw_ref_text": ref}, _ctx()
    )


def test_wbc_range_converted_with_value():
    r = _row("Total Leucocyte Count", "7200", "/cumm", "4000 - 11000")
    assert r["normalized_value"] == 7.2
    assert (r["ref_low"], r["ref_high"]) == (4.0, 11.0)
    assert r["flag"] == "normal"


def test_platelets_lakhs():
    r = _row("Platelet Count", "2.45", "Lakhs/cumm", "1.5 - 4.5")
    assert r["normalized_value"] == 245.0
    assert (r["ref_low"], r["ref_high"]) == (150.0, 450.0)
    assert r["flag"] == "normal"


def test_percent_differential_maps_to_pct():
    r = _row("Eosinophils", "3", "%", "1 - 6")
    assert r["biomarker_key"] == "eosinophils_pct"
    assert r["normalized_value"] == 3.0 and r["flag"] == "normal"
