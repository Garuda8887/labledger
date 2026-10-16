from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class JobRead(BaseModel):
    id: str
    type: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    payload: dict[str, Any] = {}
    progress: float = 0.0
    error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
