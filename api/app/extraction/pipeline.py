"""Extraction pipeline entrypoint for the job worker.

Primary API: `process_document(document_id, session=...)`.

Also supports standalone file processing for CLI / tests without a full Document row.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.extraction.classify import classify_pdf_page, classify_source
from app.extraction.digital import extract_digital_pdf, render_pdf_page_bgr
from app.extraction.ingest import resolve_stored_path
from app.extraction.layout import parse_pages
from app.extraction.metadata import extract_metadata
from app.extraction.normalize_bridge import normalize_candidates
from app.extraction.ocr import get_ocr_adapter
from app.extraction.plugins import get_extractor_plugin
from app.extraction.preprocess import preprocess_bgr, preprocess_image
from app.extraction.types import PageContent
from app.schemas.extractor import ExtractorRow

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    document_id: str | None
    status: str  # needs_review | failed
    source_type: str | None = None
    page_count: int = 0
    meta: dict[str, Any] = field(default_factory=dict)
    rows_extracted: int = 0
    rows_persisted: int = 0
    error: str | None = None
    candidates: list[Any] = field(default_factory=list)


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_iso_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s)
        d = date.fromisoformat(s[:10])
        return datetime(d.year, d.month, d.day)
    except ValueError:
        return None


def extract_pages_from_file(path: Path, mime: str) -> tuple[str, list[PageContent]]:
    """Run classify → digital/OCR → PageContent list. Returns (source_type, pages)."""
    source_type, kinds = classify_source(path, mime)
    pages: list[PageContent] = []
    ocr = get_ocr_adapter(settings.ocr_engine)

    if mime == "application/pdf" or path.suffix.lower() == ".pdf":
        import fitz

        with fitz.open(path) as doc:
            # Pre-extract digital words for digital pages
            digital_pages = {
                p.page_number: p for p in extract_digital_pdf(path) if p.kind == "digital"
            }
            for i in range(doc.page_count):
                kind = kinds[i] if i < len(kinds) else classify_pdf_page(doc, i)
                if kind == "digital" and (i + 1) in digital_pages and digital_pages[i + 1].words:
                    pages.append(digital_pages[i + 1])
                    continue
                # Scanned / weak text layer → render + OCR
                bgr, w, h = render_pdf_page_bgr(path, i, dpi=200)
                bgr = preprocess_bgr(bgr, do_perspective=False, do_deskew=True)
                words = ocr.extract_words(bgr)
                pages.append(
                    PageContent(
                        page_number=i + 1,
                        kind="scanned",
                        words=words,
                        width=w,
                        height=h,
                    )
                )
    else:
        bgr = preprocess_image(path)
        words = ocr.extract_words(bgr)
        h, w = bgr.shape[:2]
        pages.append(
            PageContent(
                page_number=1,
                kind="scanned",
                words=words,
                width=float(w),
                height=float(h),
            )
        )
        source_type = "image"

    # Optional plugin merge (never replaces rule-based; appends with source=plugin)
    plugin = get_extractor_plugin(settings.extractor_plugin)
    if plugin is not None:
        plugin_rows: list[ExtractorRow] = []
        for p in pages:
            plugin_rows.extend(list(plugin.extract_from_page(p)))
        # Stash on first page via attribute for caller — better: return separately
        # We attach as a private list for process_file to merge.
        for p in pages:
            setattr(p, "_plugin_rows", [])
        if pages:
            setattr(pages[0], "_plugin_rows", plugin_rows)

    return source_type, pages


def process_file(
    path: Path | str,
    *,
    mime: str | None = None,
    session: Session | None = None,
    profile_id: str | None = None,
) -> PipelineResult:
    """Standalone extraction (no Document required). Does not persist unless session+ids given."""
    path = Path(path)
    if mime is None:
        mime = "application/pdf" if path.suffix.lower() == ".pdf" else "image/png"
    try:
        source_type, pages = extract_pages_from_file(path, mime)
        meta = extract_metadata(pages)
        rows = parse_pages(pages)
        # Merge plugin rows if any
        if pages and getattr(pages[0], "_plugin_rows", None):
            rows = list(rows) + list(pages[0]._plugin_rows)
        candidates = normalize_candidates(rows, session=session, profile_id=profile_id)
        return PipelineResult(
            document_id=None,
            status="needs_review",
            source_type=source_type,
            page_count=len(pages),
            meta={
                "lab_name": meta.lab_name,
                "report_date": meta.report_date,
                "collected_at": meta.collected_at,
                "sample_id": meta.sample_id,
                "printed_patient_name": meta.printed_patient_name,
                "printed_patient_age": meta.printed_patient_age,
                "printed_patient_sex": meta.printed_patient_sex,
            },
            rows_extracted=len(rows),
            candidates=candidates,
        )
    except Exception as e:  # noqa: BLE001 — pipeline must not crash worker
        logger.exception("process_file failed for %s", path)
        return PipelineResult(
            document_id=None,
            status="failed",
            error=str(e),
        )


def _persist_candidates(
    session: Session,
    *,
    document_id: str,
    profile_id: str,
    candidates: list[Any],
    collected_at: datetime | None,
) -> int:
    from app.models.entities import Result

    n = 0
    for c in candidates:
        result = Result(
            document_id=document_id,
            profile_id=profile_id,
            page=c.page,
            bbox=c.bbox,
            raw_test_name=c.raw_test_name,
            raw_value=c.raw_value,
            raw_unit=c.raw_unit,
            raw_ref_text=c.raw_ref_text,
            biomarker_id=c.biomarker_id,
            comparator=c.comparator,
            value_numeric=c.value_numeric,
            value_qualitative=c.value_qualitative,
            normalized_value=c.normalized_value,
            canonical_unit=c.canonical_unit,
            ref_low=c.ref_low,
            ref_high=c.ref_high,
            ref_source=c.ref_source,
            flag=c.flag,
            collected_at=collected_at,
            confidence=c.confidence,
            confidence_reasons=c.confidence_reasons,
            status="pending_review",
        )
        session.add(result)
        n += 1
    return n


def process_document(
    document_id: str,
    session: Session | None = None,
    *,
    db: Session | None = None,
) -> PipelineResult:
    """Entrypoint for A's job worker: load Document, extract, persist pending_review rows.

    Accepts `db=` (A's job worker) or positional/keyword `session=`.
    Updates Document.status to needs_review or failed; fills metadata fields when found.
    """
    from app.db import session as db_session
    from app.models.entities import Document, Result

    db = db if db is not None else session
    own_session = db is None
    db = db or db_session.SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if doc is None:
            return PipelineResult(
                document_id=document_id,
                status="failed",
                error=f"Document {document_id} not found",
            )

        doc.status = "processing"
        db.commit()

        try:
            path = resolve_stored_path(doc.stored_path)
        except FileNotFoundError as e:
            doc.status = "failed"
            db.commit()
            return PipelineResult(document_id=document_id, status="failed", error=str(e))

        # Page rasters for review UI (files/<profile>/<sha>/pages/{n}.png)
        pdf_page_count = 0
        if doc.mime == "application/pdf" or path.suffix.lower() == ".pdf":
            from app.extraction.digital import render_pdf_pages_to_dir
            from app.services import storage as a_storage

            try:
                pdf_page_count = render_pdf_pages_to_dir(
                    path, a_storage.pages_dir(doc.profile_id, doc.sha256)
                )
            except Exception:  # noqa: BLE001 — rasters must not fail extraction
                logger.exception("page raster failed id=%s", document_id)

        file_result = process_file(
            path,
            mime=doc.mime,
            session=db,
            profile_id=doc.profile_id,
        )
        if file_result.status == "failed":
            doc.status = "failed"
            db.commit()
            return PipelineResult(
                document_id=document_id,
                status="failed",
                error=file_result.error,
            )

        # Update document metadata (non-destructive: only fill blanks)
        m = file_result.meta
        if m.get("lab_name") and not doc.lab_name:
            doc.lab_name = m["lab_name"]
        rd = _parse_iso_date(m.get("report_date"))
        if rd and not doc.report_date:
            doc.report_date = rd
        ca = _parse_iso_dt(m.get("collected_at"))
        if ca and not doc.collected_at:
            doc.collected_at = ca
        if m.get("sample_id") and not doc.sample_id:
            doc.sample_id = m["sample_id"]
        if m.get("printed_patient_name") and not doc.printed_patient_name:
            doc.printed_patient_name = m["printed_patient_name"]
        if m.get("printed_patient_age") and not doc.printed_patient_age:
            doc.printed_patient_age = m["printed_patient_age"]
        if m.get("printed_patient_sex") and not doc.printed_patient_sex:
            doc.printed_patient_sex = m["printed_patient_sex"]
        if file_result.source_type:
            doc.source_type = file_result.source_type
        if pdf_page_count:
            doc.page_count = pdf_page_count
        elif file_result.page_count:
            doc.page_count = file_result.page_count

        # Replace any prior pending rows for re-runs
        db.query(Result).filter(
            Result.document_id == document_id,
            Result.status == "pending_review",
        ).delete(synchronize_session=False)

        collected = doc.collected_at
        n = _persist_candidates(
            db,
            document_id=document_id,
            profile_id=doc.profile_id,
            candidates=file_result.candidates,
            collected_at=collected,
        )
        doc.status = "needs_review"
        db.commit()

        return PipelineResult(
            document_id=document_id,
            status="needs_review",
            source_type=doc.source_type,
            page_count=doc.page_count,
            meta=m,
            rows_extracted=file_result.rows_extracted,
            rows_persisted=n,
            candidates=file_result.candidates,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("process_document failed id=%s", document_id)
        try:
            doc = db.get(Document, document_id)
            if doc is not None:
                doc.status = "failed"
                db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        return PipelineResult(document_id=document_id, status="failed", error=str(e))
    finally:
        if own_session:
            db.close()
