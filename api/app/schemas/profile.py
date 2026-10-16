from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=256)
    dob: date | None = None
    sex: Literal["male", "female", "other", "unspecified"] = "unspecified"
    preferred_unit_system: Literal["conventional", "si"] = "conventional"


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    dob: date | None = None
    sex: Literal["male", "female", "other", "unspecified"] | None = None
    preferred_unit_system: Literal["conventional", "si"] | None = None


class ProfileRead(BaseModel):
    id: str
    display_name: str
    dob: date | None
    sex: str
    preferred_unit_system: str
    created_at: datetime

    model_config = {"from_attributes": True}
