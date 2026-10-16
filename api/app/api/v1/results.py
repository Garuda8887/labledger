"""Results list with filters."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Biomarker, Profile, Result
from app.schemas.result import ResultRead

router = APIRouter(tags=["results"])


class ResultListResponse(BaseModel):
    items: list[ResultRead]
    total: int


@router.get("/results", response_model=ResultListResponse)
def list_results(
    profile_id: str | None = Query(None),
    document_id: str | None = Query(None),
    biomarker_id: str | None = Query(None),
    category: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    collected_from: date | None = Query(None),
    collected_to: date | None = Query(None),
    flag: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ResultListResponse:
    if profile_id:
        if db.get(Profile, profile_id) is None:
            raise HTTPException(
                status_code=404,
                detail={"detail": "Profile not found", "code": "not_found"},
            )

    q = db.query(Result)
    if profile_id:
        q = q.filter(Result.profile_id == profile_id)
    if document_id:
        q = q.filter(Result.document_id == document_id)
    if biomarker_id:
        q = q.filter(Result.biomarker_id == biomarker_id)
    if status_filter:
        q = q.filter(Result.status == status_filter)
    if flag:
        q = q.filter(Result.flag == flag)
    if category:
        q = q.join(Biomarker, Result.biomarker_id == Biomarker.id).filter(
            Biomarker.category == category
        )
    if collected_from:
        q = q.filter(Result.collected_at >= datetime.combine(collected_from, datetime.min.time()))
    if collected_to:
        q = q.filter(Result.collected_at <= datetime.combine(collected_to, datetime.max.time()))

    total = q.count()
    items = (
        q.order_by(Result.confidence.asc(), Result.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ResultListResponse(
        items=[ResultRead.model_validate(r) for r in items],
        total=total,
    )


@router.get("/results/{result_id}", response_model=ResultRead)
def get_result(result_id: str, db: Session = Depends(get_db)) -> Result:
    result = db.get(Result, result_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"detail": "Result not found", "code": "not_found"})
    return result
