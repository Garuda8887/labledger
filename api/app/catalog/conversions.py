"""Table-driven unit conversion.

Only verified factors are applied. Unverified → ConversionUnsupported.
Special formulas (HbA1c) use offset + factor: result = (value + offset) * factor
when formula is set as (value - 2.15) * 10.929 → offset=-2.15, factor=10.929
with apply order: (value + offset) * factor when offset is negative pre-subtraction.

Actually for HbA1c: (value - 2.15) * 10.929 = value * 10.929 + (-2.15 * 10.929)
That's not the same as (value + offset) * factor with offset=-2.15.
We store formula string and apply specially, OR store offset_before.

Convention used here:
  if formula is "(value - 2.15) * 10.929": apply that
  else: result = value * factor + offset  (offset usually 0)
  For HbA1c we use formula field.

Round-trip: reverse uses 1/factor when offset==0 and no formula;
HbA1c reverse: NGSP = IFCC/10.929 + 2.15
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.catalog.units import normalize_unit, units_are_identity_equivalent

SEED_DIR = Path(__file__).resolve().parent / "seed"


class ConversionUnsupported(Exception):
    """Raised when no verified conversion path exists."""


@dataclass(frozen=True)
class ConversionFactor:
    analyte_group: str
    biomarker_keys: tuple[str, ...]
    from_unit: str
    to_unit: str
    factor: float
    offset: float
    formula: str | None
    verified: bool
    source_note: str

    def apply(self, value: float) -> float:
        if not self.verified:
            raise ConversionUnsupported(f"Unverified conversion: {self.analyte_group}")
        if self.formula == "(value - 2.15) * 10.929":
            return (value - 2.15) * 10.929
        # General: value * factor + offset (offset normally 0)
        return value * self.factor + self.offset

    def apply_reverse(self, value: float) -> float:
        if not self.verified:
            raise ConversionUnsupported(f"Unverified conversion: {self.analyte_group}")
        if self.formula == "(value - 2.15) * 10.929":
            return value / 10.929 + 2.15
        if self.factor == 0:
            raise ConversionUnsupported("Zero factor")
        return (value - self.offset) / self.factor


@lru_cache(maxsize=1)
def load_conversion_table() -> tuple[ConversionFactor, ...]:
    path = SEED_DIR / "conversions.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[ConversionFactor] = []
    for row in data:
        out.append(
            ConversionFactor(
                analyte_group=row["analyte_group"],
                biomarker_keys=tuple(row.get("biomarker_keys") or []),
                from_unit=row["from_unit"],
                to_unit=row["to_unit"],
                factor=float(row["factor"]),
                offset=float(row.get("offset") or 0.0),
                formula=row.get("formula"),
                verified=bool(row.get("verified", False)),
                source_note=row.get("source_note") or "",
            )
        )
    return tuple(out)


def all_verified_factors() -> list[ConversionFactor]:
    return [c for c in load_conversion_table() if c.verified]


def _match_factor(
    from_unit: str,
    to_unit: str,
    biomarker_key: str | None,
) -> ConversionFactor | None:
    for c in load_conversion_table():
        if not c.verified:
            continue
        if c.from_unit == from_unit and c.to_unit == to_unit:
            if biomarker_key is None or not c.biomarker_keys or biomarker_key in c.biomarker_keys:
                return c
    return None


def convert(
    value: float,
    from_unit: str | None,
    to_unit: str | None,
    *,
    biomarker_key: str | None = None,
) -> float:
    """Convert value between units. Raises ConversionUnsupported if impossible."""
    if from_unit is None or to_unit is None:
        raise ConversionUnsupported("Missing unit")
    src = normalize_unit(from_unit) or from_unit
    dst = normalize_unit(to_unit) or to_unit

    if src == dst or units_are_identity_equivalent(src, dst):
        return float(value)

    # Count specials: /µL ↔ 10^3/µL (÷1000), Lakhs/cumm → /µL (×100000)
    special = _count_convert(value, src, dst)
    if special is not None:
        return special

    fwd = _match_factor(src, dst, biomarker_key)
    if fwd is not None:
        return fwd.apply(value)

    # Try reverse table entry
    rev = _match_factor(dst, src, biomarker_key)
    if rev is not None:
        return rev.apply_reverse(value)

    # BUN/urea special target units in seed (mg/dL_urea / mg/dL_bun)
    # When converting bun→urea canonical both are mg/dL but different analytes —
    # handled via analyte-specific keys, not same-unit convert.

    raise ConversionUnsupported(f"No verified conversion {src} → {dst} for {biomarker_key}")


def _count_convert(value: float, src: str, dst: str) -> float | None:
    """Indian count unit bridges."""
    # Lakhs/cumm × 100_000 = /µL
    if src == "Lakhs/cumm" and dst in ("/µL", "10^3/µL"):
        per_ul = value * 100_000.0
        if dst == "10^3/µL":
            return per_ul / 1000.0
        return per_ul
    if dst == "Lakhs/cumm" and src in ("/µL", "10^3/µL"):
        per_ul = value * 1000.0 if src == "10^3/µL" else value
        return per_ul / 100_000.0

    # /cumm raw count → 10^3/µL: value/1000
    if src == "/µL" and dst == "10^3/µL":
        return value / 1000.0
    if src == "10^3/µL" and dst == "/µL":
        return value * 1000.0
    if src == "/µL" and dst == "10^6/µL":
        return value / 1_000_000.0
    if src == "10^6/µL" and dst == "/µL":
        return value * 1_000_000.0

    # Identity groups already handled; 10^3/µL ↔ 10^9/L etc.
    return None


def convert_to_canonical(
    value: float,
    raw_unit: str | None,
    canonical_unit: str,
    *,
    biomarker_key: str | None = None,
) -> tuple[float | None, str | None, list[str]]:
    """Convert to biomarker canonical unit.

    Returns (normalized_value, status_reason_or_None, reasons).
    status: if unit unrecognized → (None, "unit_unrecognized", reasons)
    if conversion missing → (None, "conversion_unsupported", reasons)
    """
    reasons: list[str] = []
    if raw_unit is None or str(raw_unit).strip() == "":
        # No unit given — if qualitative biomarker, caller handles; else assume already canonical
        reasons.append("unit_missing_assumed_canonical")
        return float(value), None, reasons

    norm = normalize_unit(raw_unit)
    if norm is None:
        reasons.append("unit_unrecognized")
        return None, "unit_unrecognized", reasons

    if norm == canonical_unit or units_are_identity_equivalent(norm, canonical_unit):
        return float(value), None, reasons

    try:
        out = convert(value, norm, canonical_unit, biomarker_key=biomarker_key)
        reasons.append(f"converted:{norm}->{canonical_unit}")
        return float(out), None, reasons
    except ConversionUnsupported:
        reasons.append("conversion_unsupported")
        return None, "conversion_unsupported", reasons


def convert_bun_urea(value: float, *, from_analyte: str) -> float:
    """BUN ↔ urea mass conversion (same mg/dL dimension, different analyte)."""
    if from_analyte == "bun":
        return value * 2.14
    if from_analyte == "urea":
        return value / 2.14
    raise ConversionUnsupported(f"bun/urea convert from {from_analyte}")


def factors_as_dicts() -> list[dict[str, Any]]:
    return [
        {
            "analyte_group": c.analyte_group,
            "biomarker_keys": list(c.biomarker_keys),
            "from_unit": c.from_unit,
            "to_unit": c.to_unit,
            "factor": c.factor,
            "offset": c.offset,
            "formula": c.formula,
            "verified": c.verified,
            "source_note": c.source_note,
        }
        for c in load_conversion_table()
    ]
