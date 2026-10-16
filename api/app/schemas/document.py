from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.job import JobRead


class DocumentRead(BaseModel):
    id: str
    profile_id: str
    original_filename: str
    sha256: str
    mime: str
    stored_path: str
    source_type: Literal["digital_pdf", "scanned_pdf", "image", "multi_image"]
    page_count: int
    lab_name: str | None
    report_date: date | None
    collected_at: datetime | None
    sample_id: str | None
    printed_patient_name: str | None = None
    printed_patient_age: str | None = None
    printed_patient_sex: str | None = None
    status: Literal["processing", "needs_review", "confirmed", "failed"]
    uploaded_at: datetime
    job_id: str | None = None

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentRead]
    jobs: list[JobRead]
    duplicates: list[dict] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    page_count: int
    job: JobRead | None = None
