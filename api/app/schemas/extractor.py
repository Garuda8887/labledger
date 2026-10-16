"""Shared Extractor row contract (mirrors shared/schemas/extractor-row.json)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 1
    # Source page size in the same coordinate space as x0..y1 (PDF points or OCR px).
    # When present, persisted as [x0,y0,x1,y1,pageW,pageH] for exact review overlays.
    page_width: float | None = None
    page_height: float | None = None


class ExtractorRow(BaseModel):
    """Candidate row returned by an Extractor plugin or rule-based parser."""

    raw_test_name: str
    raw_value: str
    raw_unit: str | None = None
    raw_ref_text: str | None = None
    comparator: Literal["=", "<", ">", "<=", ">="] = "="
    value_numeric: float | None = None
    value_qualitative: str | None = None
    page: int = 1
    bbox: BBox | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    confidence_reasons: list[str] = Field(default_factory=list)
    source: Literal["rule", "ocr", "plugin"] = "rule"
