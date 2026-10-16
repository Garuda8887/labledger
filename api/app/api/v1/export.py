"""Profile export/import as zip."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Profile
from app.schemas.profile import ProfileRead
from app.services.export_import import export_profile_zip, import_profile_zip

router = APIRouter(tags=["export"])


@router.get("/profiles/{profile_id}/export")
def export_profile(profile_id: str, db: Session = Depends(get_db)) -> FileResponse:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})
    try:
        path = export_profile_zip(db, profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"detail": str(exc), "code": "not_found"}) from exc
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"labledger-profile-{profile_id}.zip",
    )


@router.post("/profiles/import", response_model=ProfileRead)
async def import_profile(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> Profile:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail={"detail": "Empty upload", "code": "invalid_upload"})
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        profile = import_profile_zip(db, tmp_path, as_new=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail={"detail": f"Import failed: {exc}", "code": "import_failed"},
        ) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return profile
