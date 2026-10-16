"""Biomarker catalog list/search (C seeds data — tolerate empty).

alt_unit / alt_factor are computed from UnitConversion for the biomarker's
canonical unit so the frontend conventional↔SI toggle works against the live API.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import Biomarker, UnitConversion
from app.schemas.biomarker import BiomarkerListResponse, BiomarkerRead

router = APIRouter(prefix="/biomarkers", tags=["biomarkers"])


def _alt_from_conversions(
    canonical_unit: str,
    conversions: list[UnitConversion],
) -> tuple[str | None, float | None]:
    """Pick a simple multiply factor canonical → alternate unit.

    Prefers rows where from_unit == canonical (factor as stored).
    Falls back to reverse (to_unit == canonical → 1/factor).
    Skips non-affine (offset != 0) and same-unit analyte transforms (BUN/urea).
    """
    if not canonical_unit:
        return None, None
    canon = canonical_unit.strip()
    # Forward: canonical → other
    for uc in conversions:
        if abs(float(uc.offset or 0.0)) > 1e-12:
            continue
        if (uc.from_unit or "").strip() != canon:
            continue
        to_u = (uc.to_unit or "").strip()
        if not to_u or to_u == canon:
            continue
        factor = float(uc.factor)
        if factor == 0:
            continue
        return to_u, factor
    # Reverse: other → canonical
    for uc in conversions:
        if abs(float(uc.offset or 0.0)) > 1e-12:
            continue
        if (uc.to_unit or "").strip() != canon:
            continue
        from_u = (uc.from_unit or "").strip()
        if not from_u or from_u == canon:
            continue
        factor = float(uc.factor)
        if factor == 0:
            continue
        return from_u, 1.0 / factor
    return None, None


def _to_read(b: Biomarker, conversions: list[UnitConversion] | None = None) -> BiomarkerRead:
    convs = conversions if conversions is not None else list(b.unit_conversions or [])
    alt_unit, alt_factor = _alt_from_conversions(b.canonical_unit, convs)
    base = BiomarkerRead.model_validate(b)
    return base.model_copy(update={"alt_unit": alt_unit, "alt_factor": alt_factor})


@router.get("", response_model=BiomarkerListResponse)
def list_biomarkers(
    q: str | None = Query(None, description="Search display name, key, or aliases"),
    category: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> BiomarkerListResponse:
    query = db.query(Biomarker).options(joinedload(Biomarker.unit_conversions))
    if category:
        query = query.filter(Biomarker.category == category)

    rows = query.order_by(Biomarker.category, Biomarker.display_name).all()
    if q:
        q_lower = q.lower().strip()
        rows = [
            b
            for b in rows
            if q_lower in (b.display_name or "").lower()
            or q_lower in (b.canonical_key or "").lower()
            or any(q_lower in str(a).lower() for a in (b.aliases or []))
        ]

    total = len(rows)
    page = rows[offset : offset + limit]
    return BiomarkerListResponse(
        items=[_to_read(b) for b in page],
        total=total,
    )


@router.get("/{biomarker_id}", response_model=BiomarkerRead)
def get_biomarker(biomarker_id: str, db: Session = Depends(get_db)) -> BiomarkerRead:
    b = (
        db.query(Biomarker)
        .options(joinedload(Biomarker.unit_conversions))
        .filter(Biomarker.id == biomarker_id)
        .first()
    )
    if b is None:
        raise HTTPException(status_code=404, detail={"detail": "Biomarker not found", "code": "not_found"})
    return _to_read(b)
