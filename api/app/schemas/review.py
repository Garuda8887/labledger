from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.result import ResultRead


class ResultConfirmRequest(BaseModel):
    """Empty body ok — confirms a single result."""


class ResultEditRequest(BaseModel):
    raw_test_name: str | None = None
    raw_value: str | None = None
    raw_unit: str | None = None
    raw_ref_text: str | None = None
    biomarker_id: str | None = None
    comparator: Literal["=", "<", ">", "<=", ">="] | None = None
    value_numeric: float | None = None
    value_qualitative: str | None = None
    normalized_value: float | None = None
    canonical_unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag: Literal["low", "high", "normal", "unknown"] | None = None
    collected_at: datetime | None = None
    remember_mapping: bool = False


class ResultAddRequest(BaseModel):
    document_id: str
    profile_id: str
    page: int = 1
    bbox: list[float] | None = None
    raw_test_name: str = Field(min_length=1, max_length=512)
    raw_value: str = Field(min_length=1, max_length=256)
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
    flag: Literal["low", "high", "normal", "unknown"] = "unknown"
    collected_at: datetime | None = None
    remember_mapping: bool = False


class BulkConfirmRequest(BaseModel):
    result_ids: list[str] | None = None
    document_id: str | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class BulkConfirmResponse(BaseModel):
    confirmed: list[ResultRead]
    count: int


class LearnedAliasCreate(BaseModel):
    raw_name: str = Field(min_length=1, max_length=512)
    biomarker_id: str


class LearnedAliasRead(BaseModel):
    id: str
    raw_name_normalized: str
    biomarker_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentMetadataUpdate(BaseModel):
    lab_name: str | None = None
    report_date: date | None = None
    collected_at: datetime | None = None
    sample_id: str | None = None


class UnitPreferenceUpdate(BaseModel):
    preferred_unit_system: Literal["conventional", "si"]
