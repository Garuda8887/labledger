"""Seed ≥3 fictional profiles with ~3 years quarterly confirmed results + synthetic docs.

Trends (fabricated, no PHI):
- Aarav Mehta: slowly rising LDL, improving Vitamin D, stable thyroid
- Neha Kapoor: seasonal CRP, stable CBC
- Rohan Iyer: improving HbA1c, mild creatinine drift
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.synth.generate import DEFAULT_DIGITAL_DIR, generate_digital
from app.synth.layouts import LAYOUTS


def _dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc)


def _quarterly_dates(start: date, years: int = 3) -> list[date]:
    out: list[date] = []
    y, m = start.year, start.month
    while len(out) < years * 4:
        out.append(date(y, m, min(start.day, 28)))
        m += 3
        if m > 12:
            m -= 12
            y += 1
    return out


def _trend_ldl(i: int, n: int) -> float:
    return round(110 + (45 * i / max(n - 1, 1)), 1)


def _trend_vit_d(i: int, n: int) -> float:
    return round(18 + (24 * i / max(n - 1, 1)), 1)


def _trend_crp_seasonal(d: date) -> float:
    base = 1.0
    seasonal = 2.5 * (1 + math.cos((d.month - 1) / 12 * 2 * math.pi))
    return round(base + seasonal, 1)


def _trend_hba1c(i: int, n: int) -> float:
    return round(7.2 - (1.4 * i / max(n - 1, 1)), 1)


def _trend_crea(i: int, n: int) -> float:
    return round(0.85 + (0.25 * i / max(n - 1, 1)), 2)


PROFILES = [
    {
        "display_name": "Aarav Mehta",
        "dob": date(1982, 3, 14),
        "sex": "male",
        "preferred_unit_system": "conventional",
        "kind": "ldl_vitd",
    },
    {
        "display_name": "Neha Kapoor",
        "dob": date(1990, 7, 22),
        "sex": "female",
        "preferred_unit_system": "conventional",
        "kind": "crp_seasonal",
    },
    {
        "display_name": "Rohan Iyer",
        "dob": date(1975, 11, 5),
        "sex": "male",
        "preferred_unit_system": "si",
        "kind": "hba1c_crea",
    },
]


def _biomarker_map(session) -> dict[str, Any]:
    from app.models.entities import Biomarker

    return {b.canonical_key: b for b in session.query(Biomarker).all()}


def _ensure_pdf(layout_id: str) -> Path:
    digital = DEFAULT_DIGITAL_DIR
    path = digital / f"{layout_id}.pdf"
    if not path.exists():
        generate_digital()
    if path.exists():
        return path
    pdfs = list(digital.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError("No synthetic PDFs")
    return pdfs[0]


def _store_doc(session, profile_id: str, pdf_path: Path, *, report_date: date, lab_name: str):
    from app.models.entities import Document
    from app.services.storage import store_original

    data = pdf_path.read_bytes()
    # Unique per profile+date so UniqueConstraint(profile_id, sha256) allows quarterly copies
    sha = hashlib.sha256(data + f"{profile_id}:{report_date.isoformat()}".encode()).hexdigest()
    fname = f"{pdf_path.stem}_{report_date.isoformat()}.pdf"
    rel = store_original(profile_id, sha, fname, data)
    doc = Document(
        profile_id=profile_id,
        original_filename=fname,
        sha256=sha,
        mime="application/pdf",
        stored_path=str(rel),
        source_type="digital_pdf",
        page_count=1,
        lab_name=lab_name,
        report_date=report_date,
        collected_at=_dt(report_date),
        sample_id=f"DEMO-{report_date.strftime('%Y%m%d')}",
        printed_patient_name=None,
        status="confirmed",
    )
    session.add(doc)
    session.flush()
    return doc


def _add_result(session, *, doc, profile_id, bio, raw_name, value, unit, ref_low, ref_high, flag, collected):
    from app.models.entities import Result

    if ref_low is not None and ref_high is not None:
        ref_text = f"{ref_low} - {ref_high}"
    elif ref_high is not None:
        ref_text = f"< {ref_high}"
    elif ref_low is not None:
        ref_text = f"> {ref_low}"
    else:
        ref_text = None

    session.add(
        Result(
            document_id=doc.id,
            profile_id=profile_id,
            page=1,
            raw_test_name=raw_name,
            raw_value=str(value),
            raw_unit=unit,
            raw_ref_text=ref_text,
            biomarker_id=bio.id if bio else None,
            comparator="=",
            value_numeric=float(value),
            normalized_value=float(value),
            canonical_unit=unit,
            ref_low=ref_low,
            ref_high=ref_high,
            ref_source="report",
            flag=flag,
            collected_at=collected,
            confidence=0.95,
            confidence_reasons=["demo_seed"],
            status="confirmed",
            reviewed_at=collected,
        )
    )


def _flag_for(value: float, lo: float | None, hi: float | None) -> str:
    if lo is not None and value < lo:
        return "low"
    if hi is not None and value > hi:
        return "high"
    return "normal"


def _panel_for_kind(kind: str, i: int, n: int, d: date) -> list[dict]:
    rows = [
        {"key": "hemoglobin", "name": "Hemoglobin", "value": round(14.0 + 0.1 * math.sin(i), 2), "unit": "g/dL", "lo": 13.0, "hi": 17.0},
        {"key": "wbc", "name": "WBC Count", "value": 6.5, "unit": "10^3/µL", "lo": 4.0, "hi": 11.0},
        {"key": "platelets", "name": "Platelet Count", "value": 245, "unit": "10^3/µL", "lo": 150, "hi": 450},
        {"key": "tsh", "name": "TSH", "value": round(2.1 + 0.05 * math.sin(i / 2), 2), "unit": "µIU/mL", "lo": 0.4, "hi": 4.2},
        {"key": "glucose_fasting", "name": "Fasting Blood Sugar", "value": 95 + (i % 3), "unit": "mg/dL", "lo": 70, "hi": 100},
        {"key": "total_cholesterol", "name": "Cholesterol - Total", "value": 190 + i, "unit": "mg/dL", "lo": None, "hi": 200},
        {"key": "hdl", "name": "HDL Cholesterol", "value": 48, "unit": "mg/dL", "lo": 40, "hi": None},
        {"key": "triglycerides", "name": "Triglycerides", "value": 140, "unit": "mg/dL", "lo": None, "hi": 150},
        {"key": "sgpt", "name": "SGPT (ALT)", "value": 30, "unit": "U/L", "lo": None, "hi": 41},
        {"key": "creatinine", "name": "Serum Creatinine", "value": 0.9, "unit": "mg/dL", "lo": 0.7, "hi": 1.3},
    ]
    if kind == "ldl_vitd":
        rows.append({"key": "ldl", "name": "LDL Cholesterol", "value": _trend_ldl(i, n), "unit": "mg/dL", "lo": None, "hi": 130.0})
        rows.append({"key": "vitamin_d", "name": "25-OH Vitamin D", "value": _trend_vit_d(i, n), "unit": "ng/mL", "lo": 30.0, "hi": 100.0})
        rows.append({"key": "crp", "name": "CRP", "value": 1.2, "unit": "mg/L", "lo": None, "hi": 3.0})
    elif kind == "crp_seasonal":
        for r in rows:
            if r["key"] == "hemoglobin":
                r["value"], r["lo"], r["hi"] = 12.8, 12.0, 15.0
        rows.append({"key": "ldl", "name": "LDL Cholesterol", "value": 108.0, "unit": "mg/dL", "lo": None, "hi": 130.0})
        rows.append({"key": "vitamin_d", "name": "25-OH Vitamin D", "value": 32.0, "unit": "ng/mL", "lo": 30.0, "hi": 100.0})
        rows.append({"key": "crp", "name": "CRP", "value": _trend_crp_seasonal(d), "unit": "mg/L", "lo": None, "hi": 3.0})
    else:
        rows.append({"key": "ldl", "name": "LDL Cholesterol", "value": 125.0, "unit": "mg/dL", "lo": None, "hi": 130.0})
        rows.append({"key": "hba1c", "name": "HbA1c", "value": _trend_hba1c(i, n), "unit": "%", "lo": 4.0, "hi": 5.6})
        for r in rows:
            if r["key"] == "creatinine":
                r["value"] = _trend_crea(i, n)
        rows.append({"key": "vitamin_d", "name": "25-OH Vitamin D", "value": 28.0, "unit": "ng/mL", "lo": 30.0, "hi": 100.0})
        rows.append({"key": "crp", "name": "CRP", "value": 1.5, "unit": "mg/L", "lo": None, "hi": 3.0})
    return rows


def seed_demo(*, reset_demo_profiles: bool = True) -> dict[str, Any]:
    from app.catalog.seed_loader import seed_catalog
    from app.db.session import SessionLocal, init_db
    from app.models.entities import Document, Profile, Result

    init_db()
    if not DEFAULT_DIGITAL_DIR.exists() or not list(DEFAULT_DIGITAL_DIR.glob("*.pdf")):
        print("[seed-demo] generating digital synthetics…")
        generate_digital()

    db = SessionLocal()
    summary: dict[str, Any] = {"profiles": [], "documents": 0, "results": 0}
    try:
        summary["catalog"] = seed_catalog(db)
        bmap = _biomarker_map(db)

        demo_names = {p["display_name"] for p in PROFILES}
        if reset_demo_profiles:
            for p in db.query(Profile).filter(Profile.display_name.in_(demo_names)).all():
                db.query(Result).filter(Result.profile_id == p.id).delete()
                db.query(Document).filter(Document.profile_id == p.id).delete()
                db.delete(p)
            db.commit()

        dates = _quarterly_dates(date(2023, 1, 15), years=3)
        n = len(dates)
        layout_cycle = [L.id for L in LAYOUTS]

        for pi, spec in enumerate(PROFILES):
            prof = Profile(
                display_name=spec["display_name"],
                dob=spec["dob"],
                sex=spec["sex"],
                preferred_unit_system=spec["preferred_unit_system"],
            )
            db.add(prof)
            db.flush()
            summary["profiles"].append({"id": prof.id, "name": prof.display_name})

            for i, d in enumerate(dates):
                layout_id = layout_cycle[(pi + i) % len(layout_cycle)]
                pdf = _ensure_pdf(layout_id)
                lab = next(L.lab_name for L in LAYOUTS if L.id == layout_id)
                doc = _store_doc(db, prof.id, pdf, report_date=d, lab_name=lab)
                summary["documents"] += 1
                for row in _panel_for_kind(spec["kind"], i, n, d):
                    bio = bmap.get(row["key"])
                    _add_result(
                        db,
                        doc=doc,
                        profile_id=prof.id,
                        bio=bio,
                        raw_name=row["name"],
                        value=row["value"],
                        unit=row["unit"],
                        ref_low=row["lo"],
                        ref_high=row["hi"],
                        flag=_flag_for(row["value"], row["lo"], row["hi"]),
                        collected=_dt(d),
                    )
                    summary["results"] += 1
            print(f"[seed-demo] {prof.display_name}: {n} reports")

        db.commit()
    finally:
        db.close()
    print(json.dumps({k: summary[k] for k in ("profiles", "documents", "results", "catalog")}, indent=2, default=str))
    return summary


if __name__ == "__main__":
    seed_demo()
