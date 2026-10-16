from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    db: str = "ok"


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
    errors: list[dict[str, Any]] | None = None


class AuthStatusResponse(BaseModel):
    locked: bool
    unlocked: bool


class UnlockRequest(BaseModel):
    passphrase: str = Field(min_length=1)


class MessageResponse(BaseModel):
    message: str
