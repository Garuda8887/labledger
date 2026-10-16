"""Cross-checks among related results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CrossCheckFinding:
    code: str
    message: str
    biomarker_keys: tuple[str, ...]


def _get(rows: dict[str, float], *keys: str) -> float | None:
    for k in keys:
        if k in rows and rows[k] is not None:
            return float(rows[k])
    return None


def run_crosschecks(normalized_by_key: dict[str, float]) -> list[CrossCheckFinding]:
    """Run all §5.5 cross-checks. Values must be in canonical units.

    Tolerances are relative/absolute and conservative (flag mismatch, don't over-fire).
    """
    findings: list[CrossCheckFinding] = []
    r = normalized_by_key

    # Lipid sum: TC ≈ HDL + LDL + VLDL
    tc = _get(r, "total_cholesterol")
    hdl = _get(r, "hdl")
    ldl = _get(r, "ldl")
    vldl = _get(r, "vldl")
    if tc is not None and hdl is not None and ldl is not None:
        parts = hdl + ldl + (vldl if vldl is not None else 0.0)
        # If VLDL missing, allow wider tolerance or skip strict check
        if vldl is not None:
            if abs(tc - parts) > max(10.0, 0.08 * tc):
                findings.append(
                    CrossCheckFinding(
                        "lipid_sum_mismatch",
                        f"total_chol {tc} vs HDL+LDL+VLDL {parts}",
                        ("total_cholesterol", "hdl", "ldl", "vldl"),
                    )
                )
        else:
            # TC ≈ HDL + LDL (+ estimated VLDL often TG/5); soft check without VLDL
            if abs(tc - (hdl + ldl)) > max(40.0, 0.2 * tc):
                findings.append(
                    CrossCheckFinding(
                        "lipid_sum_mismatch",
                        f"total_chol {tc} far from HDL+LDL {hdl + ldl} (no VLDL)",
                        ("total_cholesterol", "hdl", "ldl"),
                    )
                )

    # MCH ≈ Hb / RBC × 10  (Hb g/dL, RBC 10^6/µL → MCH pg)
    mch = _get(r, "mch")
    hb = _get(r, "hemoglobin")
    rbc = _get(r, "rbc")
    if mch is not None and hb is not None and rbc is not None and rbc != 0:
        expected = (hb / rbc) * 10.0
        if abs(mch - expected) > max(1.5, 0.08 * expected):
            findings.append(
                CrossCheckFinding(
                    "mch_formula_mismatch",
                    f"MCH {mch} vs Hb/RBC×10={expected:.2f}",
                    ("mch", "hemoglobin", "rbc"),
                )
            )

    # Total bili ≈ direct + indirect
    tb = _get(r, "bilirubin_total")
    db = _get(r, "bilirubin_direct")
    ib = _get(r, "bilirubin_indirect")
    if tb is not None and db is not None and ib is not None:
        if abs(tb - (db + ib)) > max(0.2, 0.1 * tb):
            findings.append(
                CrossCheckFinding(
                    "bilirubin_sum_mismatch",
                    f"total bili {tb} vs direct+indirect {db + ib}",
                    ("bilirubin_total", "bilirubin_direct", "bilirubin_indirect"),
                )
            )

    # A/G ratio ≈ albumin / globulin
    ag = _get(r, "ag_ratio")
    alb = _get(r, "albumin")
    glob = _get(r, "globulin")
    if ag is not None and alb is not None and glob is not None and glob != 0:
        expected = alb / glob
        if abs(ag - expected) > max(0.15, 0.1 * expected):
            findings.append(
                CrossCheckFinding(
                    "ag_ratio_mismatch",
                    f"A/G {ag} vs albumin/globulin={expected:.2f}",
                    ("ag_ratio", "albumin", "globulin"),
                )
            )

    # TC/HDL ratio
    ratio = _get(r, "tc_hdl_ratio")
    if ratio is not None and tc is not None and hdl is not None and hdl != 0:
        expected = tc / hdl
        if abs(ratio - expected) > max(0.3, 0.08 * expected):
            findings.append(
                CrossCheckFinding(
                    "tc_hdl_ratio_mismatch",
                    f"TC/HDL {ratio} vs {expected:.2f}",
                    ("tc_hdl_ratio", "total_cholesterol", "hdl"),
                )
            )

    # Differential % ≈ 100
    diff_keys = [
        "neutrophils_pct",
        "lymphocytes_pct",
        "monocytes_pct",
        "eosinophils_pct",
        "basophils_pct",
    ]
    present = {k: r[k] for k in diff_keys if k in r and r[k] is not None}
    # Need at least neutrophils + lymphocytes to attempt
    if "neutrophils_pct" in present and "lymphocytes_pct" in present and len(present) >= 3:
        total = sum(present.values())
        # Allow bands if present
        if "bands_pct" in r and r["bands_pct"] is not None:
            total += float(r["bands_pct"])
        if abs(total - 100.0) > 3.0:
            findings.append(
                CrossCheckFinding(
                    "differential_pct_sum",
                    f"differential % sum={total:.1f} (expected ≈100)",
                    tuple(present.keys()),
                )
            )

    return findings


def findings_for_key(
    findings: list[CrossCheckFinding], biomarker_key: str
) -> list[str]:
    return [f"{f.code}:{f.message}" for f in findings if biomarker_key in f.biomarker_keys]


def apply_crosschecks_to_reasons(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mutate/copy confidence_reasons on each result dict that has biomarker_key + normalized_value."""
    by_key: dict[str, float] = {}
    for row in results:
        k = row.get("biomarker_key") or row.get("canonical_key")
        v = row.get("normalized_value")
        if k and v is not None:
            by_key[k] = float(v)
    findings = run_crosschecks(by_key)
    out = []
    for row in results:
        r = dict(row)
        k = r.get("biomarker_key") or r.get("canonical_key")
        extra = findings_for_key(findings, k) if k else []
        if extra:
            reasons = list(r.get("confidence_reasons") or [])
            reasons.extend(extra)
            r["confidence_reasons"] = reasons
            # Lower confidence on mismatch
            conf = float(r.get("confidence") or 0.5)
            r["confidence"] = max(0.0, conf - 0.15 * len(extra))
        out.append(r)
    return out
