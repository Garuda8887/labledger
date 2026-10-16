"""SQLAlchemy 2.x models matching (+ Job)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    dob: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sex: Mapped[str] = mapped_column(String(32), nullable=False, default="unspecified")
    # male|female|other|unspecified
    preferred_unit_system: Mapped[str] = mapped_column(String(32), nullable=False, default="conventional")
    # conventional|si
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list[Document]] = relationship(back_populates="profile")
    results: Mapped[list[Result]] = relationship(back_populates="profile")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("profile_id", "sha256", name="uq_document_profile_sha"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # digital_pdf|scanned_pdf|image|multi_image
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    lab_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    report_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sample_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    printed_patient_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    printed_patient_age: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    printed_patient_sex: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing")
    # processing|needs_review|confirmed|failed
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    profile: Mapped[Profile] = relationship(back_populates="documents")
    results: Mapped[list[Result]] = relationship(back_populates="document")


class Biomarker(Base):
    __tablename__ = "biomarkers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    canonical_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical_unit: Mapped[str] = mapped_column(String(64), nullable=False)
    decimals: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    aliases: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    plausibility_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plausibility_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    loinc_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    unit_conversions: Mapped[list[UnitConversion]] = relationship(back_populates="biomarker")
    reference_ranges: Mapped[list[BuiltinReferenceRange]] = relationship(back_populates="biomarker")
    learned_aliases: Mapped[list[LearnedAlias]] = relationship(back_populates="biomarker")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    page: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bbox: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)  # [x0,y0,x1,y1] or [x0,y0,x1,y1,pageW,pageH]
    raw_test_name: Mapped[str] = mapped_column(String(512), nullable=False)
    raw_value: Mapped[str] = mapped_column(String(256), nullable=False)
    raw_unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_ref_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    biomarker_id: Mapped[Optional[str]] = mapped_column(ForeignKey("biomarkers.id"), nullable=True, index=True)
    comparator: Mapped[str] = mapped_column(String(8), nullable=False, default="=")
    # =|<|>|<=|>=
    value_numeric: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    value_qualitative: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    normalized_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    canonical_unit: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ref_low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ref_high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ref_source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # report|builtin
    flag: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    # low|high|normal|unknown
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_reasons: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_review")
    # pending_review|confirmed|rejected
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship(back_populates="results")
    profile: Mapped[Profile] = relationship(back_populates="results")
    biomarker: Mapped[Optional[Biomarker]] = relationship()


class UnitConversion(Base):
    __tablename__ = "unit_conversions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    biomarker_id: Mapped[Optional[str]] = mapped_column(ForeignKey("biomarkers.id"), nullable=True, index=True)
    from_unit: Mapped[str] = mapped_column(String(64), nullable=False)
    to_unit: Mapped[str] = mapped_column(String(64), nullable=False)
    factor: Mapped[float] = mapped_column(Float, nullable=False)
    offset: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    biomarker: Mapped[Optional[Biomarker]] = relationship(back_populates="unit_conversions")


class BuiltinReferenceRange(Base):
    __tablename__ = "builtin_reference_ranges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    biomarker_id: Mapped[str] = mapped_column(ForeignKey("biomarkers.id"), nullable=False, index=True)
    sex: Mapped[str] = mapped_column(String(32), nullable=False, default="unspecified")
    age_min_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    age_max_years: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    low: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    high: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    source_note: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    biomarker: Mapped[Biomarker] = relationship(back_populates="reference_ranges")


class LearnedAlias(Base):
    __tablename__ = "learned_aliases"
    __table_args__ = (UniqueConstraint("raw_name_normalized", name="uq_learned_alias_raw"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    raw_name_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    biomarker_id: Mapped[str] = mapped_column(ForeignKey("biomarkers.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    biomarker: Mapped[Biomarker] = relationship(back_populates="learned_aliases")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    field_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    """SQLite-backed background job (no Redis/Celery)."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    # queued|running|succeeded|failed|cancelled
    payload: Mapped[Any] = mapped_column(JSON, nullable=False, default=dict)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
