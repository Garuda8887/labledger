"""Result object schemas (mirrors shared/schemas/result.json)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ResultBase(BaseModel):
    page: int = 1
    bbox: list[float] | None = None
    raw_test_name: str
    raw_value: str
    raw_unit: str | None = None
    raw_ref_text: str | None = None
    biomarker_id: str | None = None
    comparator: Literal["=", "<", ">", "<=", ">="] = "="
    value_numeric: float | None = None
    value_qualitative: str | None = None
    normalized_value: float | None = None
    canonical_unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    ref_source: Literal["report", "builtin"] | None = None
    flag: Literal["low", "high", "normal", "unknown"] = "unknown"
    collected_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    confidence_reasons: list[str] = Field(default_factory=list)
    status: Literal["pending_review", "confirmed", "rejected"] = "pending_review"


class ResultCreate(ResultBase):
    document_id: str
    profile_id: str


class ResultUpdate(BaseModel):
    raw_test_name: str | None = None
    raw_value: str | None = None
    raw_unit: str | None = None
    biomarker_id: str | None = None
    value_numeric: float | None = None
    value_qualitative: str | None = None
    normalized_value: float | None = None
    canonical_unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag: Literal["low", "high", "normal", "unknown"] | None = None
    status: Literal["pending_review", "confirmed", "rejected"] | None = None
    confidence_reasons: list[str] | None = None


class ResultRead(ResultBase):
    id: str
    document_id: str
    profile_id: str
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}
