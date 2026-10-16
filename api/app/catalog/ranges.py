"""Reference range parsing."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Sex = Literal["male", "female", "other", "unspecified"]


@dataclass(frozen=True)
class ParsedRange:
    low: float | None
    high: float | None
    raw_text: str
    sex_specific: bool = False
    selected_sex: str | None = None
    tier: str | None = None  # e.g. "desirable"
    notes: tuple[str, ...] = ()


_NUM = r"(\d+(?:\.\d+)?)"
_SEP = r"\s*[-–—to]+\s*"


def _f(s: str) -> float:
    return float(s)


def parse_reference_range(
    text: str | None,
    *,
    sex: Sex | str | None = None,
) -> ParsedRange | None:
    """Parse printed reference text into low/high.

    Supported formats:
    - `13.0 - 17.0`, `13.0–17.0`, `13.0 to 17.0`
    - `< 200`, `<=200`, `≤ 200`, `Up to 40`, `Upto 40`
    - `> 30`, `>=30`, `≥ 30`
    - `Male: x–y / Female: x–y` (and variants)
    - Multi-tier: `Desirable < 200, Borderline 200–239, High ≥ 240`
      → derive low/high from desirable/normal tier
    """
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None

    sex_n = (sex or "unspecified").lower()
    notes: list[str] = []

    # Sex-specific table
    sex_parsed = _parse_sex_specific(raw, sex_n)
    if sex_parsed is not None:
        return sex_parsed

    # Multi-tier desirable
    tier_parsed = _parse_multi_tier(raw)
    if tier_parsed is not None:
        return tier_parsed

    # Simple comparators / intervals
    simple = _parse_simple(raw)
    if simple is not None:
        return simple

    notes.append("range_unparsed")
    return ParsedRange(low=None, high=None, raw_text=raw, notes=tuple(notes))


def _parse_simple(raw: str) -> ParsedRange | None:
    s = raw.strip()
    # Range a - b
    m = re.search(rf"{_NUM}{_SEP}{_NUM}", s, re.I)
    if m and not re.search(r"desirable|borderline|high|low|optimal", s, re.I):
        # Avoid matching inside multi-tier; multi-tier handled earlier
        low, high = _f(m.group(1)), _f(m.group(2))
        if low > high:
            low, high = high, low
        return ParsedRange(low=low, high=high, raw_text=raw)

    # Up to N / Upto N
    m = re.search(rf"(?:up\s*to|upto)\s*{_NUM}", s, re.I)
    if m:
        return ParsedRange(low=None, high=_f(m.group(1)), raw_text=raw)

    # < N / <= N / ≤ N
    m = re.match(rf"^[<>]=?\s*{_NUM}\s*$", s) or re.match(
        rf"^(?:≤|>=|≤|≥)\s*{_NUM}\s*$", s
    )
    # Explicit patterns
    m = re.search(rf"(?:^|[\s,;])(?:<=|≤|<)\s*{_NUM}\b", s)
    if m and not re.search(r"desirable|borderline", s, re.I):
        # Check it's the dominant pattern (short text)
        if len(s) < 40 or re.match(rf"^\s*(?:<=|≤|<)\s*{_NUM}\s*$", s):
            return ParsedRange(low=None, high=_f(m.group(1)), raw_text=raw)
    m = re.match(rf"^\s*(?:<=|≤|<)\s*{_NUM}\s*$", s)
    if m:
        return ParsedRange(low=None, high=_f(m.group(1)), raw_text=raw)

    m = re.match(rf"^\s*(?:>=|≥|>)\s*{_NUM}\s*$", s)
    if m:
        return ParsedRange(low=_f(m.group(1)), high=None, raw_text=raw)

    return None


def _parse_sex_specific(raw: str, sex: str) -> ParsedRange | None:
    # Male: 13-17 Female: 12-15  OR  Male 13.0–17.0 / Female 12.0–15.0
    pattern = re.compile(
        rf"(male|males|men|man)\s*[:\-]?\s*{_NUM}{_SEP}{_NUM}"
        rf".*?"
        rf"(female|females|women|woman)\s*[:\-]?\s*{_NUM}{_SEP}{_NUM}",
        re.I | re.S,
    )
    m = pattern.search(raw)
    if not m:
        # Female first
        pattern2 = re.compile(
            rf"(female|females|women|woman)\s*[:\-]?\s*{_NUM}{_SEP}{_NUM}"
            rf".*?"
            rf"(male|males|men|man)\s*[:\-]?\s*{_NUM}{_SEP}{_NUM}",
            re.I | re.S,
        )
        m2 = pattern2.search(raw)
        if not m2:
            return None
        f_lo, f_hi = _f(m2.group(2)), _f(m2.group(3))
        m_lo, m_hi = _f(m2.group(5)), _f(m2.group(6))
    else:
        m_lo, m_hi = _f(m.group(2)), _f(m.group(3))
        f_lo, f_hi = _f(m.group(5)), _f(m.group(6))

    if sex in ("male", "m", "man", "men"):
        return ParsedRange(
            low=m_lo, high=m_hi, raw_text=raw, sex_specific=True, selected_sex="male"
        )
    if sex in ("female", "f", "woman", "women"):
        return ParsedRange(
            low=f_lo, high=f_hi, raw_text=raw, sex_specific=True, selected_sex="female"
        )
    # Unknown sex — return None lows with note via unparsed sex pick
    return ParsedRange(
        low=None,
        high=None,
        raw_text=raw,
        sex_specific=True,
        selected_sex=None,
        notes=("sex_required_for_range",),
    )


def _parse_multi_tier(raw: str) -> ParsedRange | None:
    if not re.search(r"desirable|optimal|normal|borderline|high", raw, re.I):
        return None

    # Desirable < 200
    m = re.search(rf"(?:desirable|optimal|normal)\s*[:=]?\s*(?:<=|≤|<)\s*{_NUM}", raw, re.I)
    if m:
        return ParsedRange(
            low=None, high=_f(m.group(1)), raw_text=raw, tier="desirable"
        )

    # Desirable 70-99 or Normal: 13-17
    m = re.search(
        rf"(?:desirable|optimal|normal)\s*[:=]?\s*{_NUM}{_SEP}{_NUM}", raw, re.I
    )
    if m:
        return ParsedRange(
            low=_f(m.group(1)), high=_f(m.group(2)), raw_text=raw, tier="desirable"
        )

    # "Desirable <200, Borderline 200-239, High >=240"
    m = re.search(rf"desirable\s*<\s*{_NUM}", raw, re.I)
    if m:
        return ParsedRange(
            low=None, high=_f(m.group(1)), raw_text=raw, tier="desirable"
        )

    return None


def compute_flag(
    value: float | None,
    low: float | None,
    high: float | None,
    *,
    comparator: str = "=",
) -> str:
    """Return low|high|normal|unknown from value and range."""
    if value is None:
        return "unknown"
    if low is None and high is None:
        return "unknown"

    # For comparators like <0.5 with range, still compare numeric value
    v = float(value)
    if low is not None and v < low:
        return "low"
    if high is not None and v > high:
        return "high"
    # At boundaries: inclusive normal
    if low is not None and high is not None and low <= v <= high:
        return "normal"
    if low is not None and high is None and v >= low:
        return "normal"
    if high is not None and low is None and v <= high:
        return "normal"
    return "unknown"


def printed_flag_mismatch(
    computed: str,
    printed_flag: str | None,
) -> str | None:
    """If report printed H/L disagrees with recomputed flag, return reason string."""
    if not printed_flag:
        return None
    p = printed_flag.strip().upper()
    mapping = {
        "H": "high",
        "HIGH": "high",
        "L": "low",
        "LOW": "low",
        "N": "normal",
        "NORMAL": "normal",
        "*": None,  # ambiguous
    }
    expected = mapping.get(p)
    if expected is None:
        return None
    if computed in ("low", "high", "normal") and computed != expected:
        return f"printed_flag_mismatch:printed={p},computed={computed}"
    return None
