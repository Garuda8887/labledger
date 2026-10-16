"""Unit string normalization.

Unknown units → None (caller marks unit_unrecognized). Never guess.
"""
from __future__ import annotations

import re
import unicodedata

# Map various micro signs / lookalikes to ASCII 'u' then re-emit as µ in canonical forms.
_MICRO_CHARS = (
    "\u00b5",  # µ MICRO SIGN
    "\u03bc",  # μ GREEK SMALL LETTER MU
    "\u0443",  # Cyrillic small u (OCR confusion) — treat cautiously; only in unit context
)

# Superscript digits → ASCII
_SUPERSCRIPT_MAP = str.maketrans({
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁺": "+", "⁻": "-",
    "₀": "0", "₁": "1", "₂": "2", "₃": "3",
})

# Multiplication / times signs
_TIMES_CHARS = ("×", "✕", "✖", "⋆", "*", "·", "⋅")

# Canonical unit forms we emit after normalization (stable strings for conversion table keys).
# Keys are fully normalized lookup forms; values are the canonical display/storage form.
_CANONICAL_UNITS: dict[str, str] = {
    # Mass / volume concentration
    "mg/dl": "mg/dL",
    "mg/dl.": "mg/dL",
    "mgm/dl": "mg/dL",
    "gm/dl": "g/dL",
    "g/dl": "g/dL",
    "gms%": "g/dL",
    "gm%": "g/dL",
    "g%": "g/dL",
    "gms/%": "g/dL",
    "g/%": "g/dL",
    "ug/dl": "µg/dL",
    "mcg/dl": "µg/dL",
    "µg/dl": "µg/dL",
    "ng/ml": "ng/mL",
    "ng/dl": "ng/dL",
    "pg/ml": "pg/mL",
    "pg/dl": "pg/dL",
    "ug/l": "µg/L",
    "mcg/l": "µg/L",
    "µg/l": "µg/L",
    "ug/ml": "µg/mL",
    "mcg/ml": "µg/mL",
    "µg/ml": "µg/mL",
    "mg/l": "mg/L",
    "g/l": "g/L",
    "nmol/l": "nmol/L",
    "umol/l": "µmol/L",
    "µmol/l": "µmol/L",
    "mmol/l": "mmol/L",
    "pmol/l": "pmol/L",
    "mmol/mol": "mmol/mol",
    # Enzyme / IU
    "u/l": "U/L",
    "iu/l": "IU/L",
    "iu/ml": "IU/mL",
    "miu/ml": "mIU/mL",
    "miu/l": "mIU/L",
    "uiu/ml": "µIU/mL",
    "µiu/ml": "µIU/mL",
    "uIU/ml".lower(): "µIU/mL",
    # Counts — Indian dialects
    "/cumm": "/µL",
    "/cu.mm": "/µL",
    "/cu mm": "/µL",
    "/cmm": "/µL",
    "cells/ul": "/µL",
    "cells/µl": "/µL",
    "/ul": "/µL",
    "/µl": "/µL",
    "thou/mm3": "10^3/µL",
    "thou/cumm": "10^3/µL",
    "thousands/cumm": "10^3/µL",
    "10^3/ul": "10^3/µL",
    "10^3/µl": "10^3/µL",
    "10e3/ul": "10^3/µL",
    "x10^3/ul": "10^3/µL",
    "x10^3/µl": "10^3/µL",
    "10^9/l": "10^9/L",
    "x10^9/l": "10^9/L",
    "10^6/ul": "10^6/µL",
    "10^6/µl": "10^6/µL",
    "10e6/ul": "10^6/µL",
    "x10^6/ul": "10^6/µL",
    "x10^6/µl": "10^6/µL",
    "10^12/l": "10^12/L",
    "x10^12/l": "10^12/L",
    "mill/cumm": "10^6/µL",
    "millions/cumm": "10^6/µL",
    "lakhs/cumm": "Lakhs/cumm",
    "lakh/cumm": "Lakhs/cumm",
    "lacs/cumm": "Lakhs/cumm",
    "lac/cumm": "Lakhs/cumm",
    # Percent / ratio / misc
    "%": "%",
    "percent": "%",
    "ratio": "ratio",
    "index": "index",
    "fl": "fL",
    "pg": "pg",
    "sec": "sec",
    "secs": "sec",
    "seconds": "sec",
    "min": "min",
    "mm/hr": "mm/hr",
    "mm/h": "mm/hr",
    "mmhg": "mmHg",
    "meq/l": "mEq/L",
    "mq/l": "mEq/L",
    "ml/min/1.73m2": "mL/min/1.73m²",
    "ml/min/1.73m²": "mL/min/1.73m²",
    "ml/min": "mL/min",
    "/hpf": "/HPF",
    "/lpf": "/LPF",
    "eu/dl": "EU/dL",
    "ng/dl": "ng/dL",
    "ug/dl": "µg/dL",
    # Identity SI equivalents kept distinct where needed
    "qualitative": "qualitative",
}


def _strip_accents_keep_micro(s: str) -> str:
    """NFKC normalize but preserve intentional micro handling via later steps."""
    return unicodedata.normalize("NFKC", s)


def preprocess_unit_string(raw: str | None) -> str:
    """Lower-case collapsed form used as lookup key (not the emitted canonical)."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    # Superscripts BEFORE NFKC (NFKC would flatten ¹⁰ → 10 without a caret)
    s = re.sub(
        r"([0-9A-Za-z])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)",
        lambda m: m.group(1) + "^" + m.group(2).translate(_SUPERSCRIPT_MAP),
        s,
    )
    s = s.translate(_SUPERSCRIPT_MAP)
    for ch in _MICRO_CHARS:
        s = s.replace(ch, "u")
    for ch in _TIMES_CHARS:
        s = s.replace(ch, "x")
    # NFKC after intentional transforms
    s = unicodedata.normalize("NFKC", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*/\s*", "/", s)
    s = re.sub(r"\s*\^\s*", "^", s)
    s = re.sub(r"\s+", "", s)
    s = s.lower()
    s = s.replace("10**", "10^")
    s = re.sub(r"10e([0-9]+)", r"10^\1", s)
    return s


def normalize_unit(raw: str | None) -> str | None:
    """Return canonical unit string, or None if unrecognized (do not guess)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    key = preprocess_unit_string(text)
    if not key:
        return None
    if key in _CANONICAL_UNITS:
        return _CANONICAL_UNITS[key]
    # Try without trailing periods
    key2 = key.rstrip(".")
    if key2 in _CANONICAL_UNITS:
        return _CANONICAL_UNITS[key2]
    # Try x10^N forms already in map; also "×10³/µL" etc. covered by preprocess
    return None


# Identity / synonym groups: same physical unit, interchangeable without factor.
# Used by conversion when from_unit and to_unit land in the same group.
UNIT_IDENTITY_GROUPS: list[frozenset[str]] = [
    frozenset({"µIU/mL", "mIU/L"}),  #
    frozenset({"ng/mL", "µg/L"}),
    frozenset({"pg/mL", "ng/L"}),
    frozenset({"10^3/µL", "10^9/L", "thou/mm³"}),  # thou/mm3 normalizes to 10^3/µL
    frozenset({"10^6/µL", "10^12/L"}),
    frozenset({"U/L", "IU/L"}),  # often treated identical for enzymes on Indian reports
    frozenset({"mEq/L", "mmol/L"}),  # for monovalent electrolytes Na/K/Cl/HCO3
]


def units_are_identity_equivalent(a: str, b: str) -> bool:
    if a == b:
        return True
    for group in UNIT_IDENTITY_GROUPS:
        if a in group and b in group:
            return True
    return False
