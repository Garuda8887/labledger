"""Normalize pipeline: raw extractor row → matched / converted / flagged result fields.

Aligns with shared/schemas/extractor-row.json → result.json fields.
Pure functions — no FastAPI routers. A/B import from here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.catalog.conversions import convert_to_canonical
from app.catalog.crosschecks import apply_crosschecks_to_reasons
from app.catalog.flags import check_plausibility
from app.catalog.matching import BiomarkerIndex, MatchResult
from app.catalog.ranges import compute_flag, parse_reference_range, printed_flag_mismatch
from app.catalog.units import normalize_unit

Sex = Literal["male", "female", "other", "unspecified"]

_QUALITATIVE_WORDS = re.compile(
    r"^(positive|negative|non[\s\-]?reactive|reactive|trace|nil|absent|"
    r"present|detected|not[\s\-]?detected|normal|abnormal|"
    r"clear|cloudy|yellow|amber|straw|pale\s*yellow|"
    r"a\+|a\-|b\+|b\-|ab\+|ab\-|o\+|o\-|"
    r"reactive|nonreactive)$",
    re.I,
)


@dataclass
class BiomarkerInfo:
    id: str | None
    canonical_key: str
    display_name: str
    category: str
    canonical_unit: str
    decimals: int
    aliases: list[str]
    plausibility_min: float | None
    plausibility_max: float | None


@dataclass
class BuiltinRange:
    biomarker_key: str
    sex: str
    age_min_years: float | None
    age_max_years: float | None
    low: float | None
    high: float | None
    unit: str


@dataclass
class NormalizeContext:
    index: BiomarkerIndex
    biomarkers_by_key: dict[str, BiomarkerInfo]
    builtin_ranges: list[BuiltinRange] = field(default_factory=list)
    learned_aliases: dict[str, str] = field(default_factory=dict)
    profile_sex: Sex | str = "unspecified"
    profile_dob: date | None = None
    collected_at: date | None = None


def parse_raw_value(raw_value: str) -> tuple[str, float | None, str | None]:
    """Return (comparator, value_numeric, value_qualitative)."""
    s = (raw_value or "").strip()
    if not s:
        return "=", None, None

    m = re.match(r"^(<=|>=|<|>|≤|≥)\s*(.+)$", s)
    comparator = "="
    rest = s
    if m:
        comp_map = {"≤": "<=", "≥": ">="}
        comparator = comp_map.get(m.group(1), m.group(1))
        rest = m.group(2).strip()

    # Qualitative
    if _QUALITATIVE_WORDS.match(rest) or re.search(r"[a-zA-Z]", rest) and not re.search(
        r"\d", rest
    ):
        return comparator, None, rest

    # Numeric (allow commas as thousand sep)
    num_s = rest.replace(",", "")
    mnum = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*$", num_s)
    if mnum:
        return comparator, float(mnum.group(1)), None

    # Mixed: try leading number
    mnum = re.match(r"^([+-]?\d+(?:\.\d+)?)", num_s)
    if mnum:
        return comparator, float(mnum.group(1)), None

    return comparator, None, rest


def _age_years(dob: date | None, at: date | None) -> float | None:
    if dob is None or at is None:
        return None
    return (at - dob).days / 365.25


def _select_builtin_range(
    ranges: list[BuiltinRange],
    biomarker_key: str,
    sex: str,
    age: float | None,
) -> BuiltinRange | None:
    candidates = [r for r in ranges if r.biomarker_key == biomarker_key]
    if not candidates:
        return None

    def age_ok(r: BuiltinRange) -> bool:
        if age is None:
            return r.age_min_years is None and r.age_max_years is None
        if r.age_min_years is not None and age < r.age_min_years:
            return False
        if r.age_max_years is not None and age > r.age_max_years:
            return False
        return True

    sex_l = (sex or "unspecified").lower()
    # Prefer sex-specific matching age
    for r in candidates:
        if r.sex == sex_l and age_ok(r):
            return r
    for r in candidates:
        if r.sex == "unspecified" and age_ok(r):
            return r
    # Fall back to any unspecified ignoring age if needed
    for r in candidates:
        if r.sex == sex_l:
            return r
    for r in candidates:
        if r.sex == "unspecified":
            return r
    return None


def normalize_row(
    row: dict[str, Any],
    ctx: NormalizeContext,
    *,
    printed_flag: str | None = None,
) -> dict[str, Any]:
    """Normalize one extractor row into result-shaped fields (no persistence).

    Input keys align with extractor-row.json.
    Output includes result.json fields plus biomarker_key for cross-checks.
    """
    reasons: list[str] = list(row.get("confidence_reasons") or [])
    base_conf = float(row.get("confidence") if row.get("confidence") is not None else 0.7)

    raw_name = row.get("raw_test_name") or ""
    raw_value = row.get("raw_value") or ""
    raw_unit = row.get("raw_unit")
    raw_ref = row.get("raw_ref_text")

    comparator_in = row.get("comparator") or "="
    value_numeric = row.get("value_numeric")
    value_qualitative = row.get("value_qualitative")

    if value_numeric is None and value_qualitative is None:
        comparator_in, value_numeric, value_qualitative = parse_raw_value(raw_value)
    comparator = comparator_in

    match: MatchResult = ctx.index.match(raw_name, learned_aliases=ctx.learned_aliases)
    reasons.extend(match.reasons)

    biomarker_key = match.biomarker_key
    biomarker_id = match.biomarker_id
    # Differential rows ("Eosinophils 3 %") share a name with their absolute count;
    # the printed unit decides which analyte it is.
    if biomarker_key and raw_unit:
        is_pct = normalize_unit(raw_unit) == "%"
        for suffix, other in (("_abs", "_pct"), ("_pct", "_abs")):
            if biomarker_key.endswith(suffix) and (is_pct == (other == "_pct")):
                alt = biomarker_key[: -len(suffix)] + other
                if alt in ctx.biomarkers_by_key:
                    biomarker_key = alt
                    biomarker_id = ctx.biomarkers_by_key[alt].id
                    reasons.append(f"unit_disambiguated:{alt}")
                break
    bm = ctx.biomarkers_by_key.get(biomarker_key) if biomarker_key else None
    if bm and biomarker_id is None:
        biomarker_id = bm.id

    normalized_value: float | None = None
    canonical_unit: str | None = None
    flag = "unknown"
    ref_low: float | None = None
    ref_high: float | None = None
    ref_source: str | None = None

    if match.method == "unmatched":
        base_conf = min(base_conf, 0.4)
        reasons.append("unmatched_biomarker")

    if bm and value_numeric is not None:
        canonical_unit = bm.canonical_unit
        if bm.canonical_unit == "qualitative":
            # Numeric shouldn't happen often
            normalized_value = float(value_numeric)
        else:
            nv, err, creasons = convert_to_canonical(
                float(value_numeric),
                raw_unit,
                bm.canonical_unit,
                biomarker_key=bm.canonical_key,
            )
            reasons.extend(creasons)
            if err == "unit_unrecognized":
                base_conf = min(base_conf, 0.35)
                normalized_value = None
            elif err == "conversion_unsupported":
                base_conf = min(base_conf, 0.4)
                # Keep raw numeric if units already look like canonical after norm fail
                nu = normalize_unit(raw_unit) if raw_unit else None
                if nu == bm.canonical_unit:
                    normalized_value = float(value_numeric)
                else:
                    normalized_value = None
            else:
                normalized_value = float(f"{nv:.10g}") if nv is not None else None

        # Plausibility
        if normalized_value is not None:
            suspect = check_plausibility(
                normalized_value, bm.plausibility_min, bm.plausibility_max
            )
            if suspect:
                reasons.append(suspect)
                base_conf = min(base_conf, 0.25)

        # Reference range: report first, then builtin
        parsed = parse_reference_range(raw_ref, sex=ctx.profile_sex)
        if parsed and (parsed.low is not None or parsed.high is not None):
            ref_low, ref_high = parsed.low, parsed.high
            ref_source = "report"
            if normalized_value is not None and bm.canonical_unit != "qualitative":
                # Range is printed in the report's unit; bring it to canonical so the
                # flag compares like with like (e.g. 4000-11000 /cumm vs 7.2 10^3/µL).
                def _cv(v):
                    if v is None:
                        return None
                    out, err, _ = convert_to_canonical(
                        float(v), raw_unit, bm.canonical_unit, biomarker_key=bm.canonical_key
                    )
                    return out if err is None else None

                lo, hi = _cv(ref_low), _cv(ref_high)
                if (ref_low is not None and lo is None) or (ref_high is not None and hi is None):
                    ref_low = ref_high = None
                    ref_source = None
                    reasons.append("ref_unit_conversion_failed")
                else:
                    ref_low, ref_high = lo, hi
            if parsed.notes:
                reasons.extend(parsed.notes)
        else:
            age = _age_years(ctx.profile_dob, ctx.collected_at)
            br = _select_builtin_range(
                ctx.builtin_ranges, bm.canonical_key, str(ctx.profile_sex), age
            )
            if br:
                ref_low, ref_high = br.low, br.high
                ref_source = "builtin"
            elif parsed and parsed.notes:
                reasons.extend(parsed.notes)

        flag = compute_flag(normalized_value, ref_low, ref_high, comparator=comparator)
        mm = printed_flag_mismatch(flag, printed_flag)
        if mm:
            reasons.append(mm)
            base_conf = min(base_conf, 0.55)

    elif value_qualitative is not None:
        # Qualitative result
        flag = "unknown"
        if bm:
            canonical_unit = bm.canonical_unit or "qualitative"

    # Match method confidence tweaks
    if match.method == "fuzzy":
        base_conf = min(base_conf, 0.75)
    # Never boost past the extractor's ceiling when OCR / missing-unit / suspect
    # reasons are present — exact alias must not mint high-conf wrong rows.
    _cap_reasons = {
        "ocr_source",
        "ocr_low_word_conf",
        "ocr_value_range_implausible",
        "missing_unit",
        "unit_unrecognized",
        "unit_missing_assumed_canonical",
        "suspect_unit_or_misread",
        "conversion_unsupported",
    }
    blocked = any(r in _cap_reasons or r.startswith("suspect") for r in reasons)
    if match.method == "exact_alias" and not blocked and "unit_unrecognized" not in reasons:
        base_conf = max(base_conf, 0.85)
    if blocked:
        # Keep OCR / incomplete rows at most just under the review high-conf gate (0.85).
        base_conf = min(base_conf, 0.8)

    confidence = max(0.0, min(1.0, base_conf))

    # bbox: extractor may use object; result schema wants [x0,y0,x1,y1] or
    # [x0,y0,x1,y1,pageW,pageH] when page size is known (exact review overlays).
    bbox = row.get("bbox")
    if isinstance(bbox, dict):
        vals = [bbox.get("x0"), bbox.get("y0"), bbox.get("x1"), bbox.get("y1")]
        pw, ph = bbox.get("page_width"), bbox.get("page_height")
        if pw and ph and float(pw) > 0 and float(ph) > 0:
            vals.extend([float(pw), float(ph)])
        bbox = vals

    out: dict[str, Any] = {
        "page": row.get("page") or 1,
        "bbox": bbox,
        "raw_test_name": raw_name,
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "raw_ref_text": raw_ref,
        "biomarker_id": biomarker_id,
        "biomarker_key": biomarker_key,
        "comparator": comparator,
        "value_numeric": value_numeric,
        "value_qualitative": value_qualitative,
        "normalized_value": normalized_value,
        "canonical_unit": canonical_unit,
        "ref_low": ref_low,
        "ref_high": ref_high,
        "ref_source": ref_source,
        "flag": flag,
        "confidence": confidence,
        "confidence_reasons": reasons,
        "status": "pending_review",
        "match_method": match.method,
    }
    return out


def normalize_rows(
    rows: list[dict[str, Any]],
    ctx: NormalizeContext,
) -> list[dict[str, Any]]:
    """Normalize many rows and apply panel cross-checks."""
    normalized = [normalize_row(r, ctx) for r in rows]
    return apply_crosschecks_to_reasons(normalized)
