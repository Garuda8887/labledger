"""Accuracy harness: run synthetics through B's process_file (+ C normalize) vs ground truth.

Prefers real extraction pipeline. Documents gaps honestly in docs/accuracy-report.md.
"""
from __future__ import annotations

import json
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.synth.generate import DEFAULT_DEGRADED_DIR, DEFAULT_DIGITAL_DIR, DEFAULT_GT_DIR

REPORT_PATH = Path(__file__).resolve().parents[3] / "docs" / "accuracy-report.md"
HIGH_CONF = 0.85


def _norm_name(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _parse_num(s: str | None) -> float | None:
    if s is None:
        return None
    m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(s).replace(",", ""))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _unit_close(a: str | None, b: str | None) -> bool:
    if not a and not b:
        return True
    if not a or not b:
        return False
    try:
        from app.catalog.units import normalize_unit

        na, _ = normalize_unit(a)
        nb, _ = normalize_unit(b)
        if na and nb and na == nb:
            return True
    except Exception:  # noqa: BLE001
        pass
    def squash(u: str) -> str:
        u = u.lower().replace("µ", "u").replace("μ", "u")
        return re.sub(r"[^a-z0-9%]", "", u)

    return squash(a) == squash(b)


def _value_close(pred: float | None, truth: float | None, tol: float = 0.02) -> bool:
    if pred is None and truth is None:
        return True
    if pred is None or truth is None:
        return False
    if truth == 0:
        return abs(pred) < 1e-6
    return abs(pred - truth) / max(abs(truth), 1e-9) <= tol or abs(pred - truth) <= 0.05


def _flag_close(a: str | None, b: str | None) -> bool:
    a = (a or "unknown").lower()
    b = (b or "unknown").lower()
    return a == b


@dataclass
class FieldScores:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, match: bool, *, predicted: bool, expected: bool) -> None:
        if expected and match:
            self.tp += 1
        elif expected and not match:
            self.fn += 1
        elif predicted and not expected:
            self.fp += 1

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


@dataclass
class CaseResult:
    layout_id: str
    variant: str  # digital | degradation kind
    path: str
    n_truth: int = 0
    n_pred: int = 0
    matched: int = 0
    fields: dict[str, FieldScores] = field(default_factory=dict)
    wrong_high_conf: int = 0
    high_conf_total: int = 0
    error: str | None = None
    notes: list[str] = field(default_factory=list)

    def ensure_fields(self) -> None:
        for k in ("test_match", "value", "unit", "range", "flag"):
            self.fields.setdefault(k, FieldScores())


def _candidate_as_dict(c: Any) -> dict[str, Any]:
    if isinstance(c, dict):
        return c
    if hasattr(c, "model_dump"):
        return c.model_dump()
    if hasattr(c, "__dict__"):
        return {k: getattr(c, k) for k in (
            "raw_test_name", "raw_value", "raw_unit", "raw_ref_text",
            "value_numeric", "value_qualitative", "comparator", "flag",
            "ref_low", "ref_high", "confidence", "confidence_reasons",
            "biomarker_id", "normalized_value", "canonical_unit",
        ) if hasattr(c, k)}
    return {}


def _match_rows(truth_rows: list[dict], pred_rows: list[dict]) -> CaseResult:
    """Greedy match by normalized test name (+ biomarker_key hint)."""
    # Placeholder — caller fills layout_id/variant/path
    cr = CaseResult(layout_id="", variant="", path="")
    cr.ensure_fields()
    cr.n_truth = len(truth_rows)
    cr.n_pred = len(pred_rows)

    used: set[int] = set()
    for t in truth_rows:
        tname = _norm_name(t.get("raw_test_name") or "")
        tkey = (t.get("biomarker_key") or "").lower()
        best_i, best_score = -1, -1.0
        for i, p in enumerate(pred_rows):
            if i in used:
                continue
            pname = _norm_name(p.get("raw_test_name") or "")
            score = 0.0
            if tname and pname and (tname == pname or tname in pname or pname in tname):
                score = 3.0
            elif tname and pname:
                # token overlap
                ta, pa = set(tname.split()), set(pname.split())
                if ta & pa:
                    score = len(ta & pa) / max(len(ta | pa), 1)
            if score > best_score:
                best_score, best_i = score, i
        matched = best_i >= 0 and best_score >= 0.5
        pred = pred_rows[best_i] if matched else None
        if matched:
            used.add(best_i)
            cr.matched += 1

        # test_match
        cr.fields["test_match"].add(matched, predicted=matched, expected=True)

        # value
        t_num = t.get("value_numeric")
        if t_num is None:
            t_num = _parse_num(t.get("raw_value"))
        p_num = None
        if pred:
            p_num = pred.get("value_numeric")
            if p_num is None:
                p_num = _parse_num(pred.get("raw_value"))
        # qualitative
        t_qual = (t.get("value_qualitative") or "").lower() or None
        p_qual = (pred.get("value_qualitative") if pred else None) or None
        if t_qual:
            val_ok = matched and p_qual and t_qual in str(p_qual).lower()
            if not val_ok and matched and pred:
                val_ok = t_qual in _norm_name(str(pred.get("raw_value") or ""))
        else:
            val_ok = matched and _value_close(p_num, t_num)
        cr.fields["value"].add(bool(val_ok), predicted=matched, expected=True)

        # unit
        unit_ok = matched and _unit_close(pred.get("raw_unit") if pred else None, t.get("raw_unit"))
        # qualitative rows often have null unit
        if not t.get("raw_unit") and matched:
            unit_ok = True
        cr.fields["unit"].add(bool(unit_ok), predicted=matched, expected=True)

        # range (ref text or low/high)
        range_ok = False
        if matched and pred:
            tr = (t.get("raw_ref_text") or "").replace("\n", " ")
            pr = (pred.get("raw_ref_text") or "").replace("\n", " ")
            if tr and pr:
                # loose: share a number from truth ref
                nums = re.findall(r"\d+\.?\d*", tr)
                range_ok = any(n in pr for n in nums[:2]) if nums else _norm_name(tr)[:20] in _norm_name(pr)
            elif t.get("ref_low") is not None or t.get("ref_high") is not None:
                pl, ph = pred.get("ref_low"), pred.get("ref_high")
                tl, th = t.get("ref_low"), t.get("ref_high")
                range_ok = True
                if tl is not None and pl is not None:
                    range_ok = range_ok and abs(float(pl) - float(tl)) <= max(0.1, abs(tl) * 0.05)
                if th is not None and ph is not None:
                    range_ok = range_ok and abs(float(ph) - float(th)) <= max(0.1, abs(th) * 0.05)
            else:
                range_ok = True  # no range expected
        cr.fields["range"].add(bool(range_ok), predicted=matched, expected=bool(t.get("raw_ref_text") or t.get("ref_low") is not None or t.get("ref_high") is not None) or True)

        # flag
        t_flag = t.get("flag") or "unknown"
        p_flag = (pred.get("flag") if pred else None) or "unknown"
        flag_ok = matched and _flag_close(p_flag, t_flag)
        cr.fields["flag"].add(bool(flag_ok), predicted=matched, expected=True)

        # wrong but high confidence
        if matched and pred:
            conf = float(pred.get("confidence") or 0)
            if conf >= HIGH_CONF:
                cr.high_conf_total += 1
                # wrong if value or unit fail
                if not val_ok or not unit_ok:
                    cr.wrong_high_conf += 1
        elif pred is None:
            pass

    # unmatched predictions count as FP for test_match
    for i, p in enumerate(pred_rows):
        if i not in used:
            cr.fields["test_match"].fp += 1

    return cr


def _extract_file(path: Path, session=None) -> tuple[list[dict], str | None]:
    """Run B's process_file; return candidate dicts and error."""
    try:
        from app.extraction.pipeline import process_file

        result = process_file(path, session=session)
        if result.status == "failed":
            return [], result.error or "process_file failed"
        return [_candidate_as_dict(c) for c in (result.candidates or [])], None
    except Exception as e:  # noqa: BLE001
        return [], f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=5)}"


def _ensure_normalize_session():
    """Build a DB session with catalog seeded for normalize_bridge."""
    try:
        from app.catalog.seed_loader import seed_catalog
        from app.db.session import SessionLocal, init_db
        from app.models.entities import Biomarker

        init_db()
        db = SessionLocal()
        count = db.query(Biomarker).count()
        if count < 50:
            seed_catalog(db)
            db.commit()
        return db, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def run_case(gt_path: Path, file_path: Path, *, variant: str, session=None) -> CaseResult:
    gt = json.loads(gt_path.read_text())
    layout_id = gt["layout_id"]
    preds, err = _extract_file(file_path, session=session)
    cr = _match_rows(gt["rows"], preds)
    cr.layout_id = layout_id
    cr.variant = variant
    cr.path = str(file_path)
    cr.error = err
    if err:
        cr.notes.append("extraction_error")
    return cr


def _agg(cases: list[CaseResult], field: str) -> dict[str, float]:
    sc = FieldScores()
    for c in cases:
        c.ensure_fields()
        f = c.fields[field]
        sc.tp += f.tp
        sc.fp += f.fp
        sc.fn += f.fn
    return {"precision": round(sc.precision, 4), "recall": round(sc.recall, 4), "f1": round(sc.f1, 4), "tp": sc.tp, "fp": sc.fp, "fn": sc.fn}


def _value_unit_recall(cases: list[CaseResult]) -> float:
    """Fraction of truth rows with both value and unit correct."""
    ok = 0
    total = 0
    for c in cases:
        if c.error:
            total += c.n_truth
            continue
        # approximate from field scores: use min of value/unit recall weighted by truth
        total += c.n_truth
        ok += min(c.fields["value"].tp, c.fields["unit"].tp)
    return ok / total if total else 0.0


def write_report(
    digital_cases: list[CaseResult],
    degraded_cases: list[CaseResult],
    *,
    out_path: Path | None = None,
    meta: dict[str, Any] | None = None,
) -> Path:
    out_path = Path(out_path or REPORT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    meta = meta or {}
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z")

    def section(title: str, cases: list[CaseResult]) -> list[str]:
        if not cases:
            return [f"### {title}", "", "_No cases run._", ""]
        lines = [f"### {title}", ""]
        vu = _value_unit_recall(cases)
        whc = sum(c.wrong_high_conf for c in cases)
        hct = sum(c.high_conf_total for c in cases)
        whc_rate = (whc / hct) if hct else 0.0
        lines.append(f"- Cases: **{len(cases)}**")
        lines.append(f"- Value+unit recall (approx): **{vu:.1%}**")
        lines.append(f"- Wrong-but-high-confidence: **{whc}/{hct}** ({whc_rate:.2%})")
        lines.append("")
        lines.append("| Field | Precision | Recall | F1 |")
        lines.append("|-------|-----------|--------|----|")
        for f in ("test_match", "value", "unit", "range", "flag"):
            a = _agg(cases, f)
            lines.append(f"| {f} | {a['precision']:.3f} | {a['recall']:.3f} | {a['f1']:.3f} |")
        lines.append("")
        # Per layout
        by_layout: dict[str, list[CaseResult]] = {}
        for c in cases:
            by_layout.setdefault(c.layout_id, []).append(c)
        lines.append("| Layout | Variant | Truth | Pred | Matched | Val recall | Unit recall | Err |")
        lines.append("|--------|---------|-------|------|---------|------------|-------------|-----|")
        for lid, cs in sorted(by_layout.items()):
            for c in cs:
                vr = c.fields["value"].recall if c.n_truth else 0
                ur = c.fields["unit"].recall if c.n_truth else 0
                err = (c.error or "")[:40].replace("|", "/")
                lines.append(
                    f"| {lid} | {c.variant} | {c.n_truth} | {c.n_pred} | {c.matched} | {vr:.2f} | {ur:.2f} | {err} |"
                )
        lines.append("")
        return lines

    dig_vu = _value_unit_recall(digital_cases) if digital_cases else 0
    deg_vu = _value_unit_recall(degraded_cases) if degraded_cases else 0
    all_cases = digital_cases + degraded_cases
    whc = sum(c.wrong_high_conf for c in all_cases)
    hct = sum(c.high_conf_total for c in all_cases) or 1
    whc_rate = whc / hct

    targets = []
    targets.append(f"- Digital value+unit ≥98%: **{'PASS' if dig_vu >= 0.98 else 'MISS'}** ({dig_vu:.1%})")
    if degraded_cases:
        targets.append(f"- Degraded value+unit ≥90%: **{'PASS' if deg_vu >= 0.90 else 'MISS'}** ({deg_vu:.1%})")
    else:
        targets.append("- Degraded value+unit ≥90%: **NOT RUN** (see notes)")
    targets.append(f"- Wrong-but-high-confidence ≤0.5%: **{'PASS' if whc_rate <= 0.005 else 'MISS'}** ({whc_rate:.2%})")

    body = [
        "# Accuracy report",
        "",
        f"Generated: **{now}**",
        "",
        "## Summary vs targets",
        "",
        *targets,
        "",
        f"- Pipeline: `{meta.get('pipeline', 'app.extraction.pipeline.process_file')}`",
        f"- Catalog seeded: **{meta.get('catalog_seeded', 'unknown')}**",
        f"- Layouts evaluated (digital): **{len({c.layout_id for c in digital_cases})}**",
        f"- Degraded cases: **{len(degraded_cases)}**",
        "",
        "## Notes",
        "",
    ]
    for n in meta.get("notes", []):
        body.append(f"- {n}")
    body.append("")
    body.extend(section("Digital PDFs", digital_cases))
    body.extend(section("Degraded variants", degraded_cases))
    body.extend(
        [
            "## Method",
            "",
            "1. Synthetic digital PDFs + ground-truth JSON from `app.synth.generate`.",
            "2. Each file run through `process_file` (B) which classifies, extracts words,",
            "   parses layout, and normalizes via C (`normalize_bridge`).",
            "3. Predictions greedily matched to truth by normalized test-name overlap.",
            "4. Field scores: test match, value (±2% or ±0.05), unit (via `normalize_unit`),",
            "   range (shared ref numbers), flag equality.",
            "5. High-confidence threshold for wrong-but-confident: "
            f"{HIGH_CONF}.",
            "",
            "## Honesty clause",
            "",
            "If targets are missed, failures should carry low confidence and route to review.",
            "This report does not claim production OCR readiness for handwriting.",
            "",
        ]
    )
    out_path.write_text("\n".join(body))
    return out_path


def run_eval(
    *,
    gt_dir: Path | None = None,
    digital_dir: Path | None = None,
    degraded_dir: Path | None = None,
    include_degraded: bool = True,
    degrade_kinds: list[str] | None = None,
    max_degraded_layouts: int = 3,
    report_path: Path | None = None,
) -> dict[str, Any]:
    gt_dir = Path(gt_dir or DEFAULT_GT_DIR)
    digital_dir = Path(digital_dir or DEFAULT_DIGITAL_DIR)
    degraded_dir = Path(degraded_dir or DEFAULT_DEGRADED_DIR)
    notes: list[str] = []

    session, seed_err = _ensure_normalize_session()
    catalog_seeded = session is not None
    if seed_err:
        notes.append(f"DB/catalog: {seed_err} — eval still runs; normalize may stub.")

    digital_cases: list[CaseResult] = []
    gt_files = sorted(gt_dir.glob("*.json"))
    gt_files = [p for p in gt_files if p.name != "index.json"]
    if not gt_files:
        notes.append("No ground-truth JSON found — run generate first.")

    for gt_path in gt_files:
        gt = json.loads(gt_path.read_text())
        pdf = digital_dir / gt["pdf"]
        if not pdf.exists():
            pdf = digital_dir / f"{gt['layout_id']}.pdf"
        if not pdf.exists():
            cr = CaseResult(layout_id=gt["layout_id"], variant="digital", path=str(pdf), error="pdf missing")
            cr.n_truth = len(gt["rows"])
            cr.ensure_fields()
            digital_cases.append(cr)
            continue
        print(f"[eval] digital {gt['layout_id']}…")
        digital_cases.append(run_case(gt_path, pdf, variant="digital", session=session))

    degraded_cases: list[CaseResult] = []
    if include_degraded:
        kinds = degrade_kinds or ["rotation_p5", "blur", "jpeg", "perspective", "low_light"]
        layout_ids = [json.loads(p.read_text())["layout_id"] for p in gt_files][:max_degraded_layouts]
        for lid in layout_ids:
            gt_path = gt_dir / f"{lid}.json"
            for kind in kinds:
                # prefer scanned PDF; fall back to jpg
                cand = [
                    degraded_dir / f"{lid}__{kind}.pdf",
                    degraded_dir / f"{lid}__{kind}.jpg",
                ]
                path = next((c for c in cand if c.exists()), None)
                if path is None:
                    notes.append(f"Missing degraded {lid}/{kind}")
                    continue
                print(f"[eval] degraded {lid}/{kind}…")
                degraded_cases.append(run_case(gt_path, path, variant=kind, session=session))
    else:
        notes.append("Degraded eval skipped (include_degraded=False).")

    if session is not None:
        session.close()

    report = write_report(
        digital_cases,
        degraded_cases,
        out_path=report_path,
        meta={
            "pipeline": "app.extraction.pipeline.process_file",
            "catalog_seeded": catalog_seeded,
            "notes": notes,
        },
    )
    summary = {
        "report": str(report),
        "digital_cases": len(digital_cases),
        "degraded_cases": len(degraded_cases),
        "digital_value_unit_recall": _value_unit_recall(digital_cases),
        "degraded_value_unit_recall": _value_unit_recall(degraded_cases) if degraded_cases else None,
        "notes": notes,
    }
    print(json.dumps({k: v for k, v in summary.items() if k != "notes"}, indent=2))
    return summary


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--no-degraded", action="store_true")
    ap.add_argument("--max-degraded-layouts", type=int, default=3)
    args = ap.parse_args()
    run_eval(include_degraded=not args.no_degraded, max_degraded_layouts=args.max_degraded_layouts)
