"""Document-level metadata extraction: lab, dates, sample ID, printed patient identity."""
from __future__ import annotations

import re
from datetime import date, datetime

from app.extraction.types import DocumentMeta, PageContent, WordBox

DATE_PATTERNS = [
    # dd/mm/yyyy or dd-mm-yyyy
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"), "dmy"),
    # dd-Mon-yyyy / dd Mon yyyy
    (
        re.compile(
            r"\b(\d{1,2})[-\s](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s,](\d{4})\b",
            re.I,
        ),
        "dMonY",
    ),
    # yyyy-mm-dd
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
]

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

LAB_LABEL = re.compile(r"\b(lab(?:oratory)?|diagnostics?|pathology|clinic)\b", re.I)
SAMPLE_LABEL = re.compile(
    r"(?:sample\s*(?:id|no\.?|number)|lab\s*(?:id|no\.?|number)|accession|sid)\s*[:#]?\s*([A-Z0-9][-A-Z0-9/]{2,})",
    re.I,
)
PATIENT_LABEL = re.compile(
    r"(?:patient\s*name|name\s*of\s*patient|patient)\s*[:.]?\s*([A-Za-z][A-Za-z .']{1,60})",
    re.I,
)
AGE_LABEL = re.compile(r"\bage\s*[:.]?\s*(\d{1,3}\s*(?:Y(?:ears?)?|Yrs?|M(?:onths?)?)?)", re.I)
SEX_LABEL = re.compile(r"\b(?:sex|gender)\s*[:.]?\s*(male|female|m|f|other)\b", re.I)
REPORT_DATE_LABEL = re.compile(
    r"(?:report\s*date|reported\s*on|date\s*of\s*report|reported)\s*[:.]?\s*",
    re.I,
)
COLLECT_DATE_LABEL = re.compile(
    r"(?:collected?\s*(?:on|at|date)?|collection\s*date|sample\s*date|drawn)\s*[:.]?\s*",
    re.I,
)


def _parse_date_match(m: re.Match[str], kind: str) -> date | None:
    try:
        if kind == "dmy":
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            return date(y, mo, d)
        if kind == "dMonY":
            d = int(m.group(1))
            mo = MONTHS[m.group(2)[:3].lower()]
            y = int(m.group(3))
            return date(y, mo, d)
        if kind == "iso":
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return None


def _find_dates(text: str) -> list[date]:
    found: list[date] = []
    for pat, kind in DATE_PATTERNS:
        for m in pat.finditer(text):
            d = _parse_date_match(m, kind)
            if d and d not in found:
                found.append(d)
    return found


def _page_text(page: PageContent) -> str:
    # Reading order: sort by y then x
    words = sorted(page.words, key=lambda w: (round(w.cy / 5) * 5, w.x0))
    return " ".join(w.text for w in words)


def _top_band_text(page: PageContent, frac: float = 0.25) -> str:
    if not page.height:
        return _page_text(page)
    cutoff = page.height * frac
    words = [w for w in page.words if w.y0 <= cutoff]
    words = sorted(words, key=lambda w: (w.cy, w.x0))
    return " ".join(w.text for w in words)


def extract_lab_name(pages: list[PageContent]) -> str | None:
    if not pages:
        return None
    top = _top_band_text(pages[0], 0.2)
    # Prefer a line containing Lab/Diagnostics near the top
    lines = re.split(r"\s{2,}|\n", top)
    # Reconstruct approximate lines by y clusters already lost — use window
    words = sorted(
        [w for w in pages[0].words if not pages[0].height or w.y0 <= pages[0].height * 0.2],
        key=lambda w: (w.cy, w.x0),
    )
    if not words:
        return None
    # Take the uppermost short-ish phrase as lab letterhead candidate
    first_y = words[0].cy
    band = [w for w in words if abs(w.cy - first_y) < 12]
    candidate = " ".join(w.text for w in band).strip()
    if len(candidate) >= 3 and not re.match(r"^\d", candidate):
        # Avoid "Patient Name" etc.
        if not re.search(r"patient|report|date|age|sex|gender", candidate, re.I):
            return candidate[:256]
    # Fallback: any Lab/Diagnostics phrase in top band
    m = re.search(r"([A-Z][A-Za-z0-9 &.'-]{2,40}\s(?:Lab|Laboratory|Diagnostics|Pathology))", top)
    if m:
        return m.group(1).strip()[:256]
    return None


def extract_metadata(pages: list[PageContent]) -> DocumentMeta:
    meta = DocumentMeta()
    if not pages:
        return meta

    full = "\n".join(_page_text(p) for p in pages[:2])  # first two pages enough
    top = _top_band_text(pages[0], 0.35)

    meta.lab_name = extract_lab_name(pages)

    m = SAMPLE_LABEL.search(full)
    if m:
        meta.sample_id = m.group(1).strip()[:128]

    m = PATIENT_LABEL.search(full)
    if m:
        name = m.group(1).strip()
        # trim trailing labels
        name = re.split(r"\b(?:age|sex|gender|sample|lab)\b", name, maxsplit=1, flags=re.I)[0].strip(" :.-")
        if name:
            meta.printed_patient_name = name[:256]

    m = AGE_LABEL.search(full)
    if m:
        meta.printed_patient_age = m.group(1).strip()[:64]

    m = SEX_LABEL.search(full)
    if m:
        sex = m.group(1).lower()
        meta.printed_patient_sex = {"m": "male", "f": "female"}.get(sex, sex)[:32]

    # Dates: prefer labelled
    report_date = None
    collected = None
    for label_re, target in ((REPORT_DATE_LABEL, "report"), (COLLECT_DATE_LABEL, "collect")):
        for m in label_re.finditer(full):
            window = full[m.end() : m.end() + 40]
            dates = _find_dates(window)
            if dates:
                if target == "report" and report_date is None:
                    report_date = dates[0]
                elif target == "collect" and collected is None:
                    collected = dates[0]

    all_dates = _find_dates(top) or _find_dates(full)
    if report_date is None and all_dates:
        report_date = all_dates[0]
    if collected is None and len(all_dates) > 1:
        collected = all_dates[1]

    if report_date:
        meta.report_date = report_date.isoformat()
    if collected:
        meta.collected_at = collected.isoformat()

    return meta
