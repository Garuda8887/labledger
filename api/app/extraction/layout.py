"""Rule-based layout parser: cluster words into rows/columns; emit ExtractorRow candidates.

General heuristics — no per-lab hardcoding. Aimed at robustness across ≥12 layouts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.schemas.extractor import BBox, ExtractorRow
from app.extraction.types import PageContent, WordBox

# Header synonyms (lowercase)
HEADER_TEST = {"test", "investigation", "parameter", "analyte", "examination", "particulars", "test name", "name"}
HEADER_RESULT = {"result", "value", "observed", "observed value", "findings", "observation"}
HEADER_UNIT = {"unit", "units", "uom"}
HEADER_REF = {
    "reference",
    "ref",
    "ref.",
    "biological",
    "reference range",
    "ref range",
    "normal range",
    "biological ref interval",
    "biological reference interval",
    "interval",
}
HEADER_METHOD = {"method", "methodology", "technique"}
HEADER_FLAG = {"flag", "flags", "status", "abnormal"}

# Exact single-word header vocabulary (column left edges are taken from these).
# Short abbreviations (u, ri, val, bri) are only honoured in exact-word form and
# only inside a row that already looks like a header (test + >=2 other roles).
HEADER_WORDS: dict[str, str] = {
    **{w: "test" for w in ("test", "tests", "investigation", "investigations", "parameter", "parameters",
                           "analyte", "examination", "particulars", "name", "description")},
    **{w: "result" for w in ("result", "results", "value", "values", "val", "observed", "finding",
                             "findings", "observation", "reading")},
    **{w: "unit" for w in ("unit", "units", "uom", "u")},
    **{w: "ref" for w in ("reference", "ref", "ref.", "range", "ranges", "interval", "bri", "ri",
                          "expected", "limits", "biological")},
    **{w: "method" for w in ("method", "methodology", "technique", "tech", "instrument")},
    **{w: "flag" for w in ("flag", "flags", "*", "abnormal", "h/l", "remark", "remarks")},
}


def _header_word_role(text: str) -> str | None:
    t = text.strip().lower().strip(":()[]")
    if t in HEADER_WORDS:
        return HEADER_WORDS[t]
    return None

SECTION_HINTS = re.compile(
    r"^(complete blood|cbc|lipid|liver|kidney|renal|thyroid|diabetes|urine|"
    r"hematology|biochemistry|serology|hormones?|vitamins?|iron studies|"
    r"differential|clinical chemistry|immunology)\b",
    re.I,
)

QUALITATIVE = re.compile(
    r"^(positive|negative|reactive|non[- ]?reactive|nonreactive|trace|"
    r"nil|present|absent|detected|not detected|normal|abnormal|"
    r"clear|cloudy|acidic|alkaline)$",
    re.I,
)

COMPARATOR_RE = re.compile(r"^(<=|>=|<|>|≤|≥)\s*([+-]?\d+(?:[.,]\d+)?)$")
VALUE_RE = re.compile(r"^([+-]?\d+(?:[.,]\d+)?(?:\s*[x×]\s*10\^?[+-]?\d+)?)(.*)$", re.I)
FLAG_RE = re.compile(r"^[*]?([HL]|High|Low|Abnormal)$", re.I)
RANGE_RE = re.compile(
    r"^(?P<a>\d+(?:[.,]\d+)?)\s*[-–—to]+\s*(?P<b>\d+(?:[.,]\d+)?)$"
    r"|^(?:up\s*to|upto|<|<=|≤)\s*(?P<hi>\d+(?:[.,]\d+)?)$"
    r"|^(?:>|>=|≥)\s*(?P<lo>\d+(?:[.,]\d+)?)$",
    re.I,
)

NOISE_ROW = re.compile(
    r"(informational|not medical|synthetic fixture|confidential|page \d+|end of report|"
    r"lab director|electronically (signed|generated)|www\.|http)",
    re.I,
)

UNITISH = re.compile(
    r"^(mg/?d[lL]|g/?d[lL]|gm/?d[lL]|gms?%|g%|µ?u?IU/?m[lL]|mIU/?[lL]|IU/?[lL]|U/?[lL]|"
    r"/cumm|/cu\.?mm|cells?/µ?[lL]|thou/?mm3?|10\^?[36]/µ?[lL]|×?10\^?[369]/[lL]|"
    r"Lakhs?/cumm|mill/?cumm|ng/?m[lL]|pg/?m[lL]|µg/?d[lL]|ug/?d[lL]|%|"
    r"mmol/?[lL]|µmol/?[lL]|umol/?[lL]|f[lL]|pg|mm/?hr|mm/?h)$",
    re.I,
)


@dataclass
class RowCluster:
    y: float
    words: list[WordBox] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.text for w in sorted(self.words, key=lambda w: w.x0))

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (
            min(w.x0 for w in self.words),
            min(w.y0 for w in self.words),
            max(w.x1 for w in self.words),
            max(w.y1 for w in self.words),
        )


def _median_height(words: list[WordBox]) -> float:
    heights = sorted(w.height for w in words if w.height > 0)
    if not heights:
        return 10.0
    return heights[len(heights) // 2]


def cluster_rows(words: list[WordBox], *, y_tol_factor: float = 0.6) -> list[RowCluster]:
    if not words:
        return []
    med_h = _median_height(words)
    tol = max(3.0, med_h * y_tol_factor)
    sorted_words = sorted(words, key=lambda w: (w.cy, w.x0))
    rows: list[RowCluster] = []
    for w in sorted_words:
        if rows and abs(w.cy - rows[-1].y) <= tol:
            rows[-1].words.append(w)
            # update running y as mean
            rows[-1].y = sum(x.cy for x in rows[-1].words) / len(rows[-1].words)
        else:
            rows.append(RowCluster(y=w.cy, words=[w]))
    return rows


def _norm_header(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _match_header_role(text: str) -> str | None:
    t = _norm_header(text)
    # multi-word headers first
    for phrase, role in (
        ("biological reference interval", "ref"),
        ("biological ref interval", "ref"),
        ("reference range", "ref"),
        ("ref range", "ref"),
        ("normal range", "ref"),
        ("observed value", "result"),
        ("test name", "test"),
    ):
        if phrase in t:
            return role
    tokens = set(re.findall(r"[a-z.]+", t))
    if tokens & HEADER_TEST:
        return "test"
    if tokens & HEADER_RESULT:
        return "result"
    if tokens & HEADER_UNIT:
        return "unit"
    if tokens & HEADER_REF:
        return "ref"
    if tokens & HEADER_METHOD:
        return "method"
    if tokens & HEADER_FLAG:
        return "flag"
    return None


@dataclass
class ColumnMap:
    test: float | None = None
    result: float | None = None
    unit: float | None = None
    ref: float | None = None
    method: float | None = None
    flag: float | None = None

    def role_at(self, x: float, page_width: float) -> str:
        """Assign nearest known column role to an x coordinate."""
        cols = {
            k: v
            for k, v in {
                "test": self.test,
                "result": self.result,
                "unit": self.unit,
                "ref": self.ref,
                "method": self.method,
                "flag": self.flag,
            }.items()
            if v is not None
        }
        if not cols:
            # Heuristic fallback by page fractions
            frac = x / page_width if page_width else 0
            if frac < 0.35:
                return "test"
            if frac < 0.50:
                return "result"
            if frac < 0.62:
                return "unit"
            if frac < 0.85:
                return "ref"
            return "flag"
        # Columns are stored as header LEFT edges. A word belongs to the right-most
        # column whose left edge is <= the word's left edge (+ small tolerance).
        # Nearest-centre assignment let Flag/Method columns steal the Unit cell.
        tol = 8.0
        ordered = sorted(cols.items(), key=lambda kv: kv[1])
        role = ordered[0][0]
        for k, edge in ordered:
            if x + tol >= edge:
                role = k
        return role


def _table_starts(hr: list[tuple[str, float]]) -> list[float]:
    """x0 of each Test header that starts a table (first, or after a non-test role)."""
    starts: list[float] = []
    prev: str | None = None
    for r, x in hr:
        if r == "test" and prev != "test":
            starts.append(x)
        prev = r
    return starts


def _header_roles(row: RowCluster) -> list[tuple[str, float]]:
    """(role, left_x0) per header word in reading order."""
    out: list[tuple[str, float]] = []
    for w in sorted(row.words, key=lambda w: w.x0):
        role = _header_word_role(w.text)
        if role:
            out.append((role, w.x0))
    return out


def detect_header(rows: list[RowCluster], page_width: float) -> tuple[ColumnMap | None, int]:
    """Return (column_map, header_row_index) or (None, -1).

    Column positions are header-word LEFT edges (first word of each role).
    """
    for idx, row in enumerate(rows[:40]):
        hr = _header_roles(row)
        roles = {r for r, _ in hr}
        if "test" not in roles or len(roles - {"test"}) < 2:
            continue
        # Most header words must be header vocabulary (rejects prose rows).
        if len(hr) < 0.6 * len(row.words):
            continue
        first: dict[str, float] = {}
        for r, x in hr:
            if r in first:
                continue
            first[r] = x
        # Only the first table if repeated (multi-table handled by caller).
        tests = _table_starts(hr)
        if len(tests) >= 2:
            cut = tests[1]
            first = {}
            for r, x in hr:
                if x < cut and r not in first:
                    first[r] = x
        cmap = ColumnMap(**{k: first.get(k) for k in ("test", "result", "unit", "ref", "method", "flag")})
        return cmap, idx
    return None, -1


def _table_bands(rows: list[RowCluster], page_width: float) -> list[tuple[float, float]] | None:
    """Detect side-by-side tables: header row repeating the Test role."""
    for row in rows[:40]:
        hr = _header_roles(row)
        roles = {r for r, _ in hr}
        if "test" not in roles or len(roles - {"test"}) < 2:
            continue
        tests = _table_starts(hr)
        if len(tests) < 2:
            return None
        edges = [t - 4 for t in tests[1:]]
        bands: list[tuple[float, float]] = []
        lo = float("-inf")
        for e in edges:
            bands.append((lo, e))
            lo = e
        bands.append((lo, float("inf")))
        return bands
    return None


def _mean(xs: list[float] | None) -> float | None:
    if not xs:
        return None
    return sum(xs) / len(xs)


def _parse_value(raw: str) -> tuple[str, str, float | None, str | None, list[str]]:
    """Return (comparator, raw_value, value_numeric, value_qualitative, reasons)."""
    reasons: list[str] = []
    s = raw.strip()
    if not s:
        return "=", s, None, None, ["empty_value"]

    if QUALITATIVE.match(s):
        return "=", s, None, s.title() if s.lower() != s.upper() else s, []

    m = COMPARATOR_RE.match(s.replace(",", ""))
    if m:
        comp = m.group(1).replace("≤", "<=").replace("≥", ">=")
        num = float(m.group(2).replace(",", ""))
        return comp, s, num, None, []

    # Flag glued to value? e.g. 12.5H
    mflag = re.match(r"^([+-]?\d+(?:[.,]\d+)?)([HL])$", s, re.I)
    if mflag:
        num = float(mflag.group(1).replace(",", ""))
        return "=", mflag.group(1), num, None, ["flag_glued_to_value"]

    m = VALUE_RE.match(s.replace(",", ""))
    if m:
        num_s = m.group(1).strip()
        rest = (m.group(2) or "").strip()
        try:
            # scientific-ish 1.2 x 10^3 → leave numeric as base for now
            if re.search(r"[x×]\s*10", num_s, re.I):
                reasons.append("scientific_notation_unexpanded")
                return "=", s, None, None, reasons
            num = float(num_s.replace(",", ""))
            if rest and not UNITISH.match(rest) and not FLAG_RE.match(rest):
                # might be unit attached
                pass
            return "=", num_s if not rest else s, num, None, reasons
        except ValueError:
            reasons.append("value_parse_failed")
            return "=", s, None, None, reasons

    reasons.append("non_numeric_value")
    return "=", s, None, s, reasons


def _is_section_header(row: RowCluster, cmap: ColumnMap | None) -> bool:
    text = row.text.strip()
    if not text or len(row.words) > 8:
        return False
    # A row with content in the Result column is a data row, never a banner
    # (e.g. "GGT 24 U/L", "Vitamin B12 420 pg/mL", "Urine Protein Negative").
    if cmap and cmap.result is not None and cmap.test is not None:
        if any(w.x0 + 8 >= cmap.result for w in row.words):
            return False
    # All caps short line or known section pattern
    if SECTION_HINTS.search(text):
        return True
    letters = re.sub(r"[^A-Za-z]", "", text)
    if letters and letters.isupper() and len(text) < 60 and len(row.words) <= 5:
        # likely section banner
        if cmap and cmap.result is not None:
            # section headers usually span left or have no value column content
            xs = [w.cx for w in row.words]
            if cmap.result and min(xs) > cmap.result - 20:
                return False
        return True
    return False


def _assign_cells(row: RowCluster, cmap: ColumnMap, page_width: float) -> dict[str, list[WordBox]]:
    cells: dict[str, list[WordBox]] = {
        "test": [],
        "result": [],
        "unit": [],
        "ref": [],
        "method": [],
        "flag": [],
    }
    for w in sorted(row.words, key=lambda w: w.x0):
        # Header-less fallback only: lone H/L at far right is a flag.
        if cmap.flag is None and FLAG_RE.match(w.text) and page_width and w.cx > page_width * 0.85:
            cells["flag"].append(w)
            continue
        role = cmap.role_at(w.x0 if cmap.test is not None else w.cx, page_width)
        cells[role].append(w)
    return cells


def _join(words: list[WordBox]) -> str:
    return " ".join(w.text for w in sorted(words, key=lambda w: w.x0)).strip()


def parse_page(page: PageContent, *, _split: bool = True) -> list[ExtractorRow]:
    """Parse one page of words into ExtractorRow candidates."""
    if not page.words:
        return []

    rows = cluster_rows(page.words)
    if _split:
        bands = _table_bands(rows, page.width)
        if bands:
            out: list[ExtractorRow] = []
            for lo, hi in bands:
                sub = PageContent(
                    page_number=page.page_number,
                    kind=page.kind,
                    words=[w for w in page.words if lo <= w.x0 < hi],
                    width=page.width,
                    height=page.height,
                    image_path=page.image_path,
                )
                for r in parse_page(sub, _split=False):
                    r.confidence_reasons.append("multi_table_page")
                    out.append(r)
            return out
    cmap, header_idx = detect_header(rows, page.width)
    if cmap is None:
        cmap = ColumnMap()  # fractional fallback
        header_idx = -1
        start = 0
    else:
        start = header_idx + 1

    results: list[ExtractorRow] = []
    pending_name: str | None = None
    pending_bbox: tuple[float, float, float, float] | None = None

    for row in rows[start:]:
        text = row.text.strip()
        if not text:
            continue
        if NOISE_ROW.search(text):
            continue
        if _is_section_header(row, cmap):
            pending_name = None
            continue
        # Skip leftover header-like rows
        if _match_header_role(text) and len(row.words) <= 6:
            maybe = [_match_header_role(w.text) for w in row.words]
            if sum(1 for m in maybe if m) >= 2:
                continue

        # Repeated table header (page/section repeat), e.g. "Test Name Result Unit ..."
        hr_roles = {r for r, _ in _header_roles(row)}
        if "test" in hr_roles and len(hr_roles) >= 3:
            continue

        cells = _assign_cells(row, cmap, page.width)
        test = _join(cells["test"])
        result = _join(cells["result"])
        unit = _join(cells["unit"])
        ref = _join(cells["ref"])
        method = _join(cells["method"])
        flag = _join(cells["flag"])

        # Wrapped test name: previous row had name only
        if pending_name and not test and result:
            test = pending_name
            pending_name = None
        elif pending_name and test:
            test = f"{pending_name} {test}".strip()
            pending_name = None

        # Name-only row → wait for continuation / value on next
        if test and not result and not unit and not ref:
            # could be multi-line name
            pending_name = f"{pending_name} {test}".strip() if pending_name else test
            pending_bbox = row.bbox
            continue

        if not test and not result:
            # Wrapped unit continuation (e.g. "mill/cum" + "m" on the next line).
            if unit and results and results[-1].raw_unit and not ref:
                prev = results[-1]
                joined_u = f"{prev.raw_unit}{unit}"
                if not _unit_known(prev.raw_unit) and _unit_known(joined_u):
                    prev.raw_unit = joined_u
                    prev.confidence_reasons = [
                        r for r in prev.confidence_reasons if r != "unit_unrecognized"
                    ] + ["unit_wrapped_joined"]
                    prev.confidence = round(min(0.85, prev.confidence / 0.6 * 0.85), 4) if page.kind != "scanned" else prev.confidence
            # maybe wrapped ref continuation — skip quietly
            continue

        if not test:
            continue
        # Banner / footer text with no result and no digits (e.g. "LIPID | LIVER").
        if not result and not re.search(r"\d", text):
            continue

        # Unit may be glued into result column; split
        if not unit and result:
            parts = result.split()
            if len(parts) >= 2 and _unit_known(parts[-1]):
                unit = parts[-1]
                result = " ".join(parts[:-1])
        # Ref text bled into unit cell (e.g. no ref header detected): split it off.
        if unit and " " in unit and not _unit_known(unit):
            parts = unit.split()
            if _unit_known(parts[0]):
                ref = f"{' '.join(parts[1:])} {ref}".strip()
                unit = parts[0]

        reasons: list[str] = []
        if flag:
            reasons.append(f"printed_flag:{flag}")

        comparator, raw_value, value_numeric, value_qualitative, vreasons = _parse_value(result)
        reasons.extend(vreasons)
        if method:
            reasons.append("method_present")

        conf, creasons = _row_confidence(
            row, page, unit=unit, ref=ref, value_numeric=value_numeric, value_qualitative=value_qualitative
        )
        reasons.extend(creasons)

        x0, y0, x1, y1 = row.bbox
        if pending_bbox:
            x0 = min(x0, pending_bbox[0])
            y0 = min(y0, pending_bbox[1])
            pending_bbox = None

        source = "ocr" if page.kind == "scanned" else "rule"
        results.append(
            ExtractorRow(
                raw_test_name=test,
                raw_value=raw_value or result,
                raw_unit=unit or None,
                raw_ref_text=ref or None,
                comparator=comparator,  # type: ignore[arg-type]
                value_numeric=value_numeric,
                value_qualitative=value_qualitative,
                page=page.page_number,
                bbox=BBox(x0=x0, y0=y0, x1=x1, y1=y1, page=page.page_number, page_width=page.width or None, page_height=page.height or None),
                confidence=round(conf, 4),
                confidence_reasons=reasons,
                source=source,  # type: ignore[arg-type]
            )
        )

    return results


def _unit_known(u: str) -> bool:
    u = u.strip()
    if not u:
        return False
    if UNITISH.match(u):
        return True
    try:
        from app.catalog.units import normalize_unit

        return normalize_unit(u) is not None
    except Exception:  # noqa: BLE001
        return False


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _row_confidence(
    row: RowCluster,
    page: PageContent,
    *,
    unit: str,
    ref: str,
    value_numeric: float | None,
    value_qualitative: str | None,
) -> tuple[float, list[str]]:
    """Conservative row confidence. Never high when unit is missing/unknown or OCR is shaky."""
    reasons: list[str] = []
    confs = [w.conf for w in row.words] or [0.0]
    avg_conf = sum(confs) / len(confs)
    min_conf = min(confs)
    ocr = page.kind == "scanned"
    conf = (0.5 * avg_conf + 0.5 * min_conf) if ocr else avg_conf

    numeric = value_numeric is not None
    if numeric and not unit:
        conf = min(conf, 0.6)
        reasons.append("missing_unit")
    elif unit and not _unit_known(unit):
        conf = min(conf, 0.6)
        reasons.append("unit_unrecognized")
    if not ref:
        conf *= 0.95
        reasons.append("missing_ref")
    if value_numeric is None and value_qualitative is None:
        conf = min(conf * 0.7, 0.5)

    if ocr:
        conf *= 0.9
        reasons.append("ocr_source")
        if min_conf < 0.9:
            conf = min(conf, 0.7)
            reasons.append("ocr_low_word_conf")
        # Sanity: OCR value wildly outside printed range → likely digit misread / row mixup.
        nums = [float(n.replace(",", ".")) for n in _NUM.findall(ref or "")]
        if numeric and nums:
            hi = max(nums)
            lo = min(nums)
            if hi > 0 and (value_numeric > hi * 5 or (lo > 0 and value_numeric < lo / 5)):
                conf = min(conf, 0.5)
                reasons.append("ocr_value_range_implausible")
        elif numeric:
            conf = min(conf, 0.7)
        # High confidence on OCR is only allowed for complete, clean rows.
        if not (numeric and unit and ref and min_conf >= 0.9 and _unit_known(unit)):
            conf = min(conf, 0.8)
    return max(0.05, min(1.0, conf)), reasons


def parse_pages(pages: list[PageContent]) -> list[ExtractorRow]:
    rows: list[ExtractorRow] = []
    for p in pages:
        rows.extend(parse_page(p))
    return rows
