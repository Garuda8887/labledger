from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.db.session import get_db
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"
    return HealthResponse(status="ok" if db_status == "ok" else "degraded", version=__version__, db=db_status)
