"""Hand-off to normalization (`app.catalog.normalize`).

Converts ExtractorRow → dict, builds NormalizeContext, returns result-shaped dicts
with status=pending_review. Falls back to a pass-through stub if C is unavailable.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.schemas.extractor import ExtractorRow

logger = logging.getLogger(__name__)


@dataclass
class NormalizedCandidate:
    """ORM-friendly view over C's normalize_row dict (or stub)."""

    raw_test_name: str
    raw_value: str
    raw_unit: str | None = None
    raw_ref_text: str | None = None
    comparator: str = "="
    value_numeric: float | None = None
    value_qualitative: str | None = None
    page: int = 1
    bbox: list[float] | None = None
    biomarker_id: str | None = None
    normalized_value: float | None = None
    canonical_unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    ref_source: str | None = None
    flag: str = "unknown"
    confidence: float = 0.5
    confidence_reasons: list[str] = field(default_factory=list)
    status: str = "pending_review"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NormalizedCandidate:
        bbox = d.get("bbox")
        if isinstance(bbox, dict):
            vals = [bbox.get("x0"), bbox.get("y0"), bbox.get("x1"), bbox.get("y1")]
            pw, ph = bbox.get("page_width"), bbox.get("page_height")
            if pw and ph and float(pw) > 0 and float(ph) > 0:
                vals.extend([float(pw), float(ph)])
            bbox = vals
        elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            bbox = list(bbox)
        return cls(
            raw_test_name=d.get("raw_test_name") or "",
            raw_value=d.get("raw_value") or "",
            raw_unit=d.get("raw_unit"),
            raw_ref_text=d.get("raw_ref_text"),
            comparator=d.get("comparator") or "=",
            value_numeric=d.get("value_numeric"),
            value_qualitative=d.get("value_qualitative"),
            page=int(d.get("page") or 1),
            bbox=bbox,
            biomarker_id=d.get("biomarker_id"),
            normalized_value=d.get("normalized_value"),
            canonical_unit=d.get("canonical_unit"),
            ref_low=d.get("ref_low"),
            ref_high=d.get("ref_high"),
            ref_source=d.get("ref_source"),
            flag=d.get("flag") or "unknown",
            confidence=float(d.get("confidence") if d.get("confidence") is not None else 0.5),
            confidence_reasons=list(d.get("confidence_reasons") or []),
            status=d.get("status") or "pending_review",
        )


def _row_to_dict(r: ExtractorRow) -> dict[str, Any]:
    d = r.model_dump()
    if d.get("bbox") is not None and isinstance(d["bbox"], dict):
        # keep dict form; C accepts both
        pass
    return d


def _stub_normalize(rows: Sequence[ExtractorRow]) -> list[NormalizedCandidate]:
    out: list[NormalizedCandidate] = []
    for r in rows:
        bbox = None
        if r.bbox is not None:
            bbox = [r.bbox.x0, r.bbox.y0, r.bbox.x1, r.bbox.y1]
            if r.bbox.page_width and r.bbox.page_height:
                bbox.extend([float(r.bbox.page_width), float(r.bbox.page_height)])
        out.append(
            NormalizedCandidate(
                raw_test_name=r.raw_test_name,
                raw_value=r.raw_value,
                raw_unit=r.raw_unit,
                raw_ref_text=r.raw_ref_text,
                comparator=r.comparator,
                value_numeric=r.value_numeric,
                value_qualitative=r.value_qualitative,
                page=r.page,
                bbox=bbox,
                confidence=min(r.confidence, 0.85),
                confidence_reasons=list(r.confidence_reasons) + ["catalog_normalize_stub"],
                status="pending_review",
            )
        )
    return out


def normalize_candidates(
    rows: Sequence[ExtractorRow],
    *,
    session: Any = None,
    profile_id: str | None = None,  # reserved for profile sex/dob lookup by A/C
    profile_sex: str = "unspecified",
) -> list[NormalizedCandidate]:
    """Normalize extractor rows via C when available; else stub."""
    if not rows:
        return []
    try:
        from app.catalog.normalize import normalize_rows
        from app.catalog.seed_loader import build_normalize_context

        ctx = build_normalize_context(session)
        # Optionally enrich ctx with profile sex if we have a session + profile_id
        if session is not None and profile_id:
            try:
                from app.models.entities import Profile

                prof = session.get(Profile, profile_id)
                if prof is not None:
                    ctx.profile_sex = prof.sex or "unspecified"
                    ctx.profile_dob = prof.dob
            except Exception:  # noqa: BLE001
                logger.debug("profile enrich skipped", exc_info=True)
        elif profile_sex:
            ctx.profile_sex = profile_sex

        dicts = normalize_rows([_row_to_dict(r) for r in rows], ctx)
        return [NormalizedCandidate.from_dict(d) for d in dicts]
    except Exception:  # noqa: BLE001
        logger.warning("catalog normalize unavailable; using stub", exc_info=True)
        return _stub_normalize(rows)
