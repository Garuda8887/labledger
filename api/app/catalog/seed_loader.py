"""Load catalog seed JSON into the database. Idempotent by canonical_key."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Biomarker, BuiltinReferenceRange, UnitConversion

SEED_DIR = Path(__file__).resolve().parent / "seed"


def _uuid() -> str:
    return str(uuid.uuid4())


def load_seed_files() -> dict[str, Any]:
    return {
        "biomarkers": json.loads((SEED_DIR / "biomarkers.json").read_text(encoding="utf-8")),
        "conversions": json.loads((SEED_DIR / "conversions.json").read_text(encoding="utf-8")),
        "builtin_ranges": json.loads(
            (SEED_DIR / "builtin_ranges.json").read_text(encoding="utf-8")
        ),
    }


def seed_catalog(session: Session, *, replace_conversions: bool = True) -> dict[str, int]:
    """Upsert biomarkers, unit conversions, and builtin ranges.

    Returns counts of rows written/updated.
    """
    data = load_seed_files()
    biomarkers = data["biomarkers"]
    conversions = data["conversions"]
    ranges = data["builtin_ranges"]

    key_to_id: dict[str, str] = {}
    bm_created = bm_updated = 0

    existing = {
        b.canonical_key: b
        for b in session.scalars(select(Biomarker)).all()
    }

    for row in biomarkers:
        key = row["canonical_key"]
        if key in existing:
            b = existing[key]
            b.display_name = row["display_name"]
            b.category = row["category"]
            b.canonical_unit = row["canonical_unit"]
            b.decimals = int(row.get("decimals") or 1)
            b.aliases = list(row.get("aliases") or [])
            b.plausibility_min = row.get("plausibility_min")
            b.plausibility_max = row.get("plausibility_max")
            b.loinc_code = row.get("loinc_code")
            bm_updated += 1
        else:
            b = Biomarker(
                id=_uuid(),
                canonical_key=key,
                display_name=row["display_name"],
                category=row["category"],
                canonical_unit=row["canonical_unit"],
                decimals=int(row.get("decimals") or 1),
                aliases=list(row.get("aliases") or []),
                plausibility_min=row.get("plausibility_min"),
                plausibility_max=row.get("plausibility_max"),
                loinc_code=row.get("loinc_code"),
            )
            session.add(b)
            existing[key] = b
            bm_created += 1
        key_to_id[key] = existing[key].id

    session.flush()

    # Refresh ids after flush
    for key, b in existing.items():
        key_to_id[key] = b.id

    conv_count = 0
    if replace_conversions:
        # Remove prior seeded conversions (all rows) — catalog owns this table content
        for old in session.scalars(select(UnitConversion)).all():
            session.delete(old)
        session.flush()

    for crow in conversions:
        if not crow.get("verified", False):
            continue
        keys = crow.get("biomarker_keys") or [None]
        for bk in keys:
            bid = key_to_id.get(bk) if bk else None
            # Special target units for bun/urea cross-analyte: store as from→to with note
            to_unit = crow["to_unit"]
            # Skip synthetic mg/dL_urea targets as DB unit strings — store meaningful SI pairs only
            if to_unit in ("mg/dL_urea", "mg/dL_bun"):
                # Store with to_unit still as mg/dL and note the analyte transform
                uc = UnitConversion(
                    id=_uuid(),
                    biomarker_id=bid,
                    from_unit=crow["from_unit"],
                    to_unit="mg/dL",
                    factor=float(crow["factor"]),
                    offset=float(crow.get("offset") or 0.0),
                    source_note=f"{crow.get('source_note','')} [{crow['analyte_group']}]",
                )
            else:
                uc = UnitConversion(
                    id=_uuid(),
                    biomarker_id=bid,
                    from_unit=crow["from_unit"],
                    to_unit=to_unit,
                    factor=float(crow["factor"]),
                    offset=float(crow.get("offset") or 0.0),
                    source_note=crow.get("source_note"),
                )
            session.add(uc)
            conv_count += 1

    # Builtin ranges: replace all for simplicity (seed is source of truth)
    for old in session.scalars(select(BuiltinReferenceRange)).all():
        session.delete(old)
    session.flush()

    range_count = 0
    for rrow in ranges:
        bk = rrow["biomarker_key"]
        bid = key_to_id.get(bk)
        if not bid:
            continue
        session.add(
            BuiltinReferenceRange(
                id=_uuid(),
                biomarker_id=bid,
                sex=rrow.get("sex") or "unspecified",
                age_min_years=rrow.get("age_min_years"),
                age_max_years=rrow.get("age_max_years"),
                low=rrow.get("low"),
                high=rrow.get("high"),
                unit=rrow["unit"],
                source_note=rrow.get("source_note"),
            )
        )
        range_count += 1

    session.commit()
    return {
        "biomarkers_created": bm_created,
        "biomarkers_updated": bm_updated,
        "biomarkers_total": len(key_to_id),
        "conversions": conv_count,
        "builtin_ranges": range_count,
    }


def build_normalize_context(session: Session | None = None) -> Any:
    """Build NormalizeContext from seed files (and optional DB ids)."""
    from app.catalog.matching import BiomarkerIndex
    from app.catalog.normalize import BiomarkerInfo, BuiltinRange, NormalizeContext

    data = load_seed_files()
    key_to_id: dict[str, str | None] = {}
    learned: dict[str, str] = {}

    if session is not None:
        for b in session.scalars(select(Biomarker)).all():
            key_to_id[b.canonical_key] = b.id
        from app.models.entities import LearnedAlias

        for la in session.scalars(select(LearnedAlias)).all():
            bm = session.get(Biomarker, la.biomarker_id)
            if bm:
                learned[la.raw_name_normalized] = bm.canonical_key

    bm_dicts = []
    biomarkers_by_key: dict[str, BiomarkerInfo] = {}
    for row in data["biomarkers"]:
        key = row["canonical_key"]
        bid = key_to_id.get(key)
        d = dict(row)
        d["id"] = bid
        bm_dicts.append(d)
        biomarkers_by_key[key] = BiomarkerInfo(
            id=bid,
            canonical_key=key,
            display_name=row["display_name"],
            category=row["category"],
            canonical_unit=row["canonical_unit"],
            decimals=int(row.get("decimals") or 1),
            aliases=list(row.get("aliases") or []),
            plausibility_min=row.get("plausibility_min"),
            plausibility_max=row.get("plausibility_max"),
        )

    index = BiomarkerIndex.from_biomarkers(bm_dicts, learned_aliases=learned)
    builtin = [
        BuiltinRange(
            biomarker_key=r["biomarker_key"],
            sex=r.get("sex") or "unspecified",
            age_min_years=r.get("age_min_years"),
            age_max_years=r.get("age_max_years"),
            low=r.get("low"),
            high=r.get("high"),
            unit=r["unit"],
        )
        for r in data["builtin_ranges"]
    ]
    return NormalizeContext(
        index=index,
        biomarkers_by_key=biomarkers_by_key,
        builtin_ranges=builtin,
        learned_aliases=learned,
    )
