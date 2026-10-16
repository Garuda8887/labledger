"""Generate ≥12 fictional digital PDFs + ground-truth JSON + degraded variants."""
from __future__ import annotations

import json
import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from app.synth.degrade import DEGRADATIONS, degrade_pdf
from app.synth.layouts import LAYOUTS, LayoutSpec
from app.synth.panels import TruthRow, build_full_panel
from app.synth.pdf_render import render_report_pdf

# Default output under fixtures (committed digital + GT); degraded under data/synth
DEFAULT_DIGITAL_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "synth" / "digital"
DEFAULT_GT_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "synth" / "ground_truth"
DEFAULT_DEGRADED_DIR = Path(__file__).resolve().parents[3] / "data" / "synth" / "degraded"


def _rows_for_layout(layout: LayoutSpec, sex: str = "male") -> list[TruthRow]:
    return build_full_panel(
        sex=sex,
        ldl=138.0 if "flag" in layout.features or layout.flag_col else 118.0,
        vit_d=22.0 if layout.flag_col else 34.0,
        crp=4.5 if layout.flag_col else 1.2,
        include_comparators=layout.comparators,
        include_qualitative=layout.qualitative,
        include_si=layout.mixed_si,
        sex_specific=layout.sex_specific,
    )


def _patient_for(layout: LayoutSpec) -> dict[str, str]:
    if layout.sex_specific:
        return {
            "patient_name": "Neha Kapoor",
            "patient_age": "35 Y",
            "patient_sex": "Female",
            "sex": "female",
        }
    return {
        "patient_name": "Aarav Mehta",
        "patient_age": "42 Y",
        "patient_sex": "Male",
        "sex": "male",
    }


def write_ground_truth(
    layout: LayoutSpec,
    rows: list[TruthRow],
    pdf_path: Path,
    gt_path: Path,
    *,
    patient: dict[str, str],
    report_date: date,
    sample_id: str,
) -> dict[str, Any]:
    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    payload: dict[str, Any] = {
        "layout_id": layout.id,
        "lab_name": layout.lab_name,
        "description": layout.description,
        "features": layout.features,
        "columns": layout.columns,
        "pdf": str(pdf_path.name),
        "sha256": sha,
        "patient_name": patient["patient_name"],
        "patient_sex": patient["sex"],
        "report_date": report_date.isoformat(),
        "sample_id": sample_id,
        "source_type": "digital_pdf",
        "rows": [r.to_dict() for r in rows],
    }
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def generate_digital(
    out_dir: Path | None = None,
    gt_dir: Path | None = None,
    *,
    layouts: list[LayoutSpec] | None = None,
) -> list[dict[str, Any]]:
    out_dir = Path(out_dir or DEFAULT_DIGITAL_DIR)
    gt_dir = Path(gt_dir or DEFAULT_GT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)
    layouts = layouts or LAYOUTS
    manifests: list[dict[str, Any]] = []
    report_date = date(2024, 6, 15)

    for i, layout in enumerate(layouts):
        patient = _patient_for(layout)
        rows = _rows_for_layout(layout, sex=patient["sex"])
        # Multipage: stamp page numbers onto rows by section breaks
        if layout.multi_page and layout.page_break_after_sections:
            page = 1
            seen_breaks = 0
            for r in rows:
                r.page = page
                if r.section in layout.page_break_after_sections:
                    # after finishing this section's last row of that section name — bump when section changes
                    pass
            # Simpler: assign page by section index vs break list
            page = 1
            last_sec = None
            for r in rows:
                if last_sec is not None and r.section != last_sec and last_sec in layout.page_break_after_sections:
                    page += 1
                r.page = page
                last_sec = r.section

        sample_id = f"SYN-{i + 1:04d}"
        pdf_path = out_dir / f"{layout.id}.pdf"
        render_report_pdf(
            layout,
            rows,
            patient_name=patient["patient_name"],
            patient_age=patient["patient_age"],
            patient_sex=patient["patient_sex"],
            report_date=report_date,
            sample_id=sample_id,
            out_path=pdf_path,
        )
        gt_path = gt_dir / f"{layout.id}.json"
        payload = write_ground_truth(
            layout, rows, pdf_path, gt_path, patient=patient, report_date=report_date, sample_id=sample_id
        )
        manifests.append(payload)
        print(f"[synth] digital {layout.id}: {len(rows)} rows → {pdf_path.name}")

    index = {"count": len(manifests), "layouts": [m["layout_id"] for m in manifests]}
    (gt_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return manifests


def generate_degraded(
    digital_dir: Path | None = None,
    out_dir: Path | None = None,
    *,
    layout_ids: list[str] | None = None,
    kinds: list[str] | None = None,
    limit_layouts: int | None = None,
) -> dict[str, Any]:
    """Generate degraded variants. Defaults to all layouts × all kinds (sequential)."""
    digital_dir = Path(digital_dir or DEFAULT_DIGITAL_DIR)
    out_dir = Path(out_dir or DEFAULT_DEGRADED_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(digital_dir.glob("*.pdf"))
    if layout_ids:
        pdfs = [p for p in pdfs if p.stem in layout_ids]
    if limit_layouts is not None:
        pdfs = pdfs[:limit_layouts]
    kinds = kinds or list(DEGRADATIONS)
    summary: dict[str, Any] = {"outputs": {}, "kinds": kinds}

    for pdf in pdfs:
        # multiphoto only for first layout to save disk/RAM
        do_multi = pdf.stem == (pdfs[0].stem if pdfs else "")
        print(f"[synth] degrade {pdf.stem} ({len(kinds)} kinds)…")
        results = degrade_pdf(pdf, out_dir, kinds=kinds, stem=pdf.stem, multi_photo=do_multi)
        summary["outputs"][pdf.stem] = {k: [str(p) for p in v] for k, v in results.items()}

    (out_dir / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def generate_all(
    *,
    digital_dir: Path | None = None,
    gt_dir: Path | None = None,
    degraded_dir: Path | None = None,
    skip_degraded: bool = False,
    degrade_layout_limit: int | None = None,
) -> dict[str, Any]:
    manifests = generate_digital(digital_dir, gt_dir)
    degraded = None
    if not skip_degraded:
        degraded = generate_degraded(
            digital_dir or DEFAULT_DIGITAL_DIR,
            degraded_dir,
            limit_layouts=degrade_layout_limit,
        )
    return {"digital": manifests, "degraded": degraded, "layout_count": len(manifests)}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Generate Labledger synthetic lab reports")
    p.add_argument("--skip-degraded", action="store_true")
    p.add_argument("--degrade-limit", type=int, default=None, help="Only degrade first N layouts")
    p.add_argument("--digital-only", action="store_true")
    args = p.parse_args()
    result = generate_all(
        skip_degraded=args.skip_degraded or args.digital_only,
        degrade_layout_limit=args.degrade_limit,
    )
    print(json.dumps({"layout_count": result["layout_count"]}, indent=2))
