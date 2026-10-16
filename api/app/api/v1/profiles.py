"""Profiles CRUD + unit preference."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.logging_utils import log_event
from app.db.session import get_db
from app.models import Document, Profile, Result
from app.schemas.profile import ProfileCreate, ProfileRead, ProfileUpdate
from app.schemas.review import UnitPreferenceUpdate
from app.services import storage
from app.services.audit import record_audit

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[ProfileRead])
def list_profiles(db: Session = Depends(get_db)) -> list[Profile]:
    return db.query(Profile).order_by(Profile.created_at.asc()).all()


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)) -> Profile:
    profile = Profile(
        display_name=body.display_name,
        dob=body.dob,
        sex=body.sex,
        preferred_unit_system=body.preferred_unit_system,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    storage.profile_files_dir(profile.id)
    log_event("profile_created", profile_id=profile.id)
    return profile


@router.get("/{profile_id}", response_model=ProfileRead)
def get_profile(profile_id: str, db: Session = Depends(get_db)) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})
    return profile


@router.patch("/{profile_id}", response_model=ProfileRead)
def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    db: Session = Depends(get_db),
) -> Profile:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})
    data = body.model_dump(exclude_unset=True)
    for key, val in data.items():
        old = getattr(profile, key)
        if old != val:
            record_audit(
                db,
                entity_type="profile",
                entity_id=profile.id,
                action="update",
                field_name=key,
                old_value=str(old) if old is not None else None,
                new_value=str(val) if val is not None else None,
            )
            setattr(profile, key, val)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    log_event("profile_updated", profile_id=profile.id)
    return profile


@router.put("/{profile_id}/unit-preference", response_model=ProfileRead)
def set_unit_preference(
    profile_id: str,
    body: UnitPreferenceUpdate,
    db: Session = Depends(get_db),
) -> Profile:
    """Convenience endpoint for unit system toggle (conventional|si)."""
    return update_profile(
        profile_id,
        ProfileUpdate(preferred_unit_system=body.preferred_unit_system),
        db,
    )


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_profile(
    profile_id: str,
    confirm: bool = False,
    db: Session = Depends(get_db),
) -> Response:
    """Hard delete profile and related rows. Requires confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Pass confirm=true to permanently delete this profile",
                "code": "confirmation_required",
            },
        )
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})

    db.query(Result).filter(Result.profile_id == profile_id).delete(synchronize_session=False)
    db.query(Document).filter(Document.profile_id == profile_id).delete(synchronize_session=False)
    db.delete(profile)
    db.commit()
    storage.delete_profile_files(profile_id)
    log_event("profile_deleted", profile_id=profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
