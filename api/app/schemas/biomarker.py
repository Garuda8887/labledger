from __future__ import annotations

from pydantic import BaseModel, Field


class BiomarkerRead(BaseModel):
    id: str
    canonical_key: str
    display_name: str
    category: str
    canonical_unit: str
    decimals: int
    aliases: list[str] = Field(default_factory=list)
    plausibility_min: float | None = None
    plausibility_max: float | None = None
    loinc_code: str | None = None
    # Conventional↔SI display toggle (computed from UnitConversion; not DB columns)
    alt_unit: str | None = None
    alt_factor: float | None = None

    model_config = {"from_attributes": True}


class BiomarkerListResponse(BaseModel):
    items: list[BiomarkerRead]
    total: int
