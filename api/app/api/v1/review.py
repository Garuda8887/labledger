"""Review endpoints: confirm, edit, reject, add, bulk confirm, learned-alias."""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.logging_utils import log_event
from app.db.session import get_db
from app.models import Biomarker, Document, LearnedAlias, Profile, Result
from app.schemas.result import ResultRead
from app.schemas.review import (
    BulkConfirmRequest,
    BulkConfirmResponse,
    DocumentMetadataUpdate,
    LearnedAliasCreate,
    LearnedAliasRead,
    ResultAddRequest,
    ResultEditRequest,
)
from app.services.audit import record_audit

router = APIRouter(tags=["review"])


def _normalize_alias(raw: str) -> str:
    return " ".join(raw.strip().lower().split())


def _maybe_learn_alias(
    db: Session,
    *,
    raw_name: str | None,
    biomarker_id: str | None,
    remember: bool,
) -> LearnedAlias | None:
    if not remember or not raw_name or not biomarker_id:
        return None
    if db.get(Biomarker, biomarker_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Biomarker not found", "code": "not_found"},
        )
    norm = _normalize_alias(raw_name)
    existing = (
        db.query(LearnedAlias).filter(LearnedAlias.raw_name_normalized == norm).first()
    )
    if existing:
        if existing.biomarker_id != biomarker_id:
            existing.biomarker_id = biomarker_id
            db.add(existing)
        return existing
    alias = LearnedAlias(raw_name_normalized=norm, biomarker_id=biomarker_id)
    db.add(alias)
    return alias


def _touch_document_status(db: Session, document_id: str) -> None:
    """If all non-rejected results confirmed → document confirmed."""
    doc = db.get(Document, document_id)
    if doc is None:
        return
    pending = (
        db.query(Result)
        .filter(
            Result.document_id == document_id,
            Result.status == "pending_review",
        )
        .count()
    )
    confirmed = (
        db.query(Result)
        .filter(Result.document_id == document_id, Result.status == "confirmed")
        .count()
    )
    if pending == 0 and confirmed > 0:
        doc.status = "confirmed"
        db.add(doc)
    elif pending > 0 and doc.status == "processing":
        doc.status = "needs_review"
        db.add(doc)


@router.post("/results/{result_id}/confirm", response_model=ResultRead)
def confirm_result(result_id: str, db: Session = Depends(get_db)) -> Result:
    result = db.get(Result, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"detail": "Result not found", "code": "not_found"})
    if result.status == "rejected":
        raise HTTPException(
            status_code=400,
            detail={"detail": "Cannot confirm a rejected result", "code": "invalid_state"},
        )
    old = result.status
    result.status = "confirmed"
    result.reviewed_at = datetime.now(timezone.utc)
    db.add(result)
    record_audit(
        db,
        entity_type="result",
        entity_id=result.id,
        action="confirm",
        field_name="status",
        old_value=old,
        new_value="confirmed",
    )
    _touch_document_status(db, result.document_id)
    db.commit()
    db.refresh(result)
    log_event("result_confirmed", result_id=result.id, document_id=result.document_id)
    return result


@router.post("/results/{result_id}/reject", response_model=ResultRead)
def reject_result(result_id: str, db: Session = Depends(get_db)) -> Result:
    result = db.get(Result, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"detail": "Result not found", "code": "not_found"})
    old = result.status
    result.status = "rejected"
    result.reviewed_at = datetime.now(timezone.utc)
    db.add(result)
    record_audit(
        db,
        entity_type="result",
        entity_id=result.id,
        action="reject",
        field_name="status",
        old_value=old,
        new_value="rejected",
    )
    _touch_document_status(db, result.document_id)
    db.commit()
    db.refresh(result)
    log_event("result_rejected", result_id=result.id)
    return result


@router.patch("/results/{result_id}", response_model=ResultRead)
def edit_result(
    result_id: str,
    body: ResultEditRequest,
    db: Session = Depends(get_db),
) -> Result:
    result = db.get(Result, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"detail": "Result not found", "code": "not_found"})
    data = body.model_dump(exclude_unset=True, exclude={"remember_mapping"})
    for key, val in data.items():
        old = getattr(result, key)
        if old != val:
            record_audit(
                db,
                entity_type="result",
                entity_id=result.id,
                action="edit",
                field_name=key,
                old_value=str(old) if old is not None else None,
                new_value=str(val) if val is not None else None,
            )
            setattr(result, key, val)
    _maybe_learn_alias(
        db,
        raw_name=result.raw_test_name,
        biomarker_id=result.biomarker_id,
        remember=body.remember_mapping,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    log_event("result_edited", result_id=result.id)
    return result


@router.post("/results", response_model=ResultRead, status_code=status.HTTP_201_CREATED)
def add_result(body: ResultAddRequest, db: Session = Depends(get_db)) -> Result:
    doc = db.get(Document, body.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"detail": "Document not found", "code": "not_found"})
    if doc.profile_id != body.profile_id:
        raise HTTPException(
            status_code=400,
            detail={"detail": "profile_id does not match document", "code": "profile_mismatch"},
        )
    if db.get(Profile, body.profile_id) is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})
    if body.biomarker_id and db.get(Biomarker, body.biomarker_id) is None:
        raise HTTPException(status_code=404, detail={"detail": "Biomarker not found", "code": "not_found"})

    result = Result(
        document_id=body.document_id,
        profile_id=body.profile_id,
        page=body.page,
        bbox=body.bbox,
        raw_test_name=body.raw_test_name,
        raw_value=body.raw_value,
        raw_unit=body.raw_unit,
        raw_ref_text=body.raw_ref_text,
        biomarker_id=body.biomarker_id,
        comparator=body.comparator,
        value_numeric=body.value_numeric,
        value_qualitative=body.value_qualitative,
        normalized_value=body.normalized_value,
        canonical_unit=body.canonical_unit,
        ref_low=body.ref_low,
        ref_high=body.ref_high,
        flag=body.flag,
        collected_at=body.collected_at,
        confidence=1.0,
        confidence_reasons=["manual_entry"],
        status="pending_review",
    )
    db.add(result)
    db.flush()
    _maybe_learn_alias(
        db,
        raw_name=body.raw_test_name,
        biomarker_id=body.biomarker_id,
        remember=body.remember_mapping,
    )
    record_audit(
        db,
        entity_type="result",
        entity_id=result.id,
        action="add",
    )
    if doc.status == "processing":
        doc.status = "needs_review"
        db.add(doc)
    db.commit()
    db.refresh(result)
    log_event("result_added", result_id=result.id, document_id=doc.id)
    return result


@router.post("/results/bulk-confirm", response_model=BulkConfirmResponse)
def bulk_confirm(body: BulkConfirmRequest, db: Session = Depends(get_db)) -> BulkConfirmResponse:
    q = db.query(Result).filter(Result.status == "pending_review")
    if body.result_ids:
        q = q.filter(Result.id.in_(body.result_ids))
    elif body.document_id:
        q = q.filter(Result.document_id == body.document_id)
    else:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Provide result_ids or document_id", "code": "validation_error"},
        )
    if body.min_confidence is not None:
        q = q.filter(Result.confidence >= body.min_confidence)

    rows = q.all()
    now = datetime.now(timezone.utc)
    doc_ids: set[str] = set()
    for r in rows:
        r.status = "confirmed"
        r.reviewed_at = now
        db.add(r)
        record_audit(
            db,
            entity_type="result",
            entity_id=r.id,
            action="bulk_confirm",
            field_name="status",
            old_value="pending_review",
            new_value="confirmed",
        )
        doc_ids.add(r.document_id)
    for did in doc_ids:
        _touch_document_status(db, did)
    db.commit()
    for r in rows:
        db.refresh(r)
    log_event("results_bulk_confirmed", count=len(rows))
    return BulkConfirmResponse(
        confirmed=[ResultRead.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.post(
    "/learned-aliases",
    response_model=LearnedAliasRead,
    status_code=status.HTTP_201_CREATED,
)
def create_learned_alias(
    body: LearnedAliasCreate,
    db: Session = Depends(get_db),
) -> LearnedAlias:
    if db.get(Biomarker, body.biomarker_id) is None:
        raise HTTPException(status_code=404, detail={"detail": "Biomarker not found", "code": "not_found"})
    alias = _maybe_learn_alias(
        db,
        raw_name=body.raw_name,
        biomarker_id=body.biomarker_id,
        remember=True,
    )
    assert alias is not None
    db.commit()
    db.refresh(alias)
    log_event("learned_alias_created", alias_id=alias.id, biomarker_id=body.biomarker_id)
    return alias


@router.get("/learned-aliases", response_model=list[LearnedAliasRead])
def list_learned_aliases(db: Session = Depends(get_db)) -> list[LearnedAlias]:
    return db.query(LearnedAlias).order_by(LearnedAlias.created_at.desc()).all()


@router.patch("/documents/{document_id}/metadata", response_model=dict)
def update_document_metadata(
    document_id: str,
    body: DocumentMetadataUpdate,
    db: Session = Depends(get_db),
) -> dict:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"detail": "Document not found", "code": "not_found"})
    data = body.model_dump(exclude_unset=True)
    if "report_date" in data and data["report_date"] is not None:
        val = data["report_date"]
        if isinstance(val, datetime):
            data["report_date"] = val.date()
        elif isinstance(val, date):
            data["report_date"] = val
    for key, val in data.items():
        old = getattr(doc, key)
        if old != val:
            record_audit(
                db,
                entity_type="document",
                entity_id=doc.id,
                action="edit_metadata",
                field_name=key,
                old_value=str(old) if old is not None else None,
                new_value=str(val) if val is not None else None,
            )
            setattr(doc, key, val)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    log_event("document_metadata_updated", document_id=doc.id)
    from app.schemas.document import DocumentRead

    return DocumentRead.model_validate(doc).model_dump(mode="json")
