"""Initial schema — Profile, Document, Result, Biomarker, UnitConversion,
BuiltinReferenceRange, LearnedAlias, AuditLog, Job.

Revision ID: 001
Revises:
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(32), nullable=False, server_default="unspecified"),
        sa.Column("preferred_unit_system", sa.String(32), nullable=False, server_default="conventional"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "biomarkers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("canonical_key", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("canonical_unit", sa.String(64), nullable=False),
        sa.Column("decimals", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("plausibility_min", sa.Float(), nullable=True),
        sa.Column("plausibility_max", sa.Float(), nullable=True),
        sa.Column("loinc_code", sa.String(32), nullable=True),
    )
    op.create_index("ix_biomarkers_canonical_key", "biomarkers", ["canonical_key"], unique=True)
    op.create_index("ix_biomarkers_category", "biomarkers", ["category"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("mime", sa.String(128), nullable=False),
        sa.Column("stored_path", sa.String(1024), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("lab_name", sa.String(256), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sample_id", sa.String(128), nullable=True),
        sa.Column("printed_patient_name", sa.String(256), nullable=True),
        sa.Column("printed_patient_age", sa.String(64), nullable=True),
        sa.Column("printed_patient_sex", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("profile_id", "sha256", name="uq_document_profile_sha"),
    )
    op.create_index("ix_documents_profile_id", "documents", ["profile_id"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])

    op.create_table(
        "results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("raw_test_name", sa.String(512), nullable=False),
        sa.Column("raw_value", sa.String(256), nullable=False),
        sa.Column("raw_unit", sa.String(64), nullable=True),
        sa.Column("raw_ref_text", sa.Text(), nullable=True),
        sa.Column("biomarker_id", sa.String(36), sa.ForeignKey("biomarkers.id"), nullable=True),
        sa.Column("comparator", sa.String(8), nullable=False, server_default="="),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_qualitative", sa.String(128), nullable=True),
        sa.Column("normalized_value", sa.Float(), nullable=True),
        sa.Column("canonical_unit", sa.String(64), nullable=True),
        sa.Column("ref_low", sa.Float(), nullable=True),
        sa.Column("ref_high", sa.Float(), nullable=True),
        sa.Column("ref_source", sa.String(32), nullable=True),
        sa.Column("flag", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("confidence_reasons", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_review"),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_results_document_id", "results", ["document_id"])
    op.create_index("ix_results_profile_id", "results", ["profile_id"])
    op.create_index("ix_results_biomarker_id", "results", ["biomarker_id"])

    op.create_table(
        "unit_conversions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("biomarker_id", sa.String(36), sa.ForeignKey("biomarkers.id"), nullable=True),
        sa.Column("from_unit", sa.String(64), nullable=False),
        sa.Column("to_unit", sa.String(64), nullable=False),
        sa.Column("factor", sa.Float(), nullable=False),
        sa.Column("offset", sa.Float(), nullable=False, server_default="0"),
        sa.Column("source_note", sa.String(512), nullable=True),
    )
    op.create_index("ix_unit_conversions_biomarker_id", "unit_conversions", ["biomarker_id"])

    op.create_table(
        "builtin_reference_ranges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("biomarker_id", sa.String(36), sa.ForeignKey("biomarkers.id"), nullable=False),
        sa.Column("sex", sa.String(32), nullable=False, server_default="unspecified"),
        sa.Column("age_min_years", sa.Float(), nullable=True),
        sa.Column("age_max_years", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(64), nullable=False),
        sa.Column("source_note", sa.String(512), nullable=True),
    )
    op.create_index("ix_builtin_reference_ranges_biomarker_id", "builtin_reference_ranges", ["biomarker_id"])

    op.create_table(
        "learned_aliases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("raw_name_normalized", sa.String(512), nullable=False),
        sa.Column("biomarker_id", sa.String(36), sa.ForeignKey("biomarkers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("raw_name_normalized", name="uq_learned_alias_raw"),
    )
    op.create_index("ix_learned_aliases_biomarker_id", "learned_aliases", ["biomarker_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("actor", sa.String(64), nullable=False, server_default="user"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_type", "jobs", ["type"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("audit_logs")
    op.drop_table("learned_aliases")
    op.drop_table("builtin_reference_ranges")
    op.drop_table("unit_conversions")
    op.drop_table("results")
    op.drop_table("documents")
    op.drop_table("biomarkers")
    op.drop_table("profiles")
