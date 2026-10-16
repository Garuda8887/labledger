from fastapi import APIRouter, Depends

from app.api.v1 import (
    auth,
    biomarkers,
    documents,
    export,
    health,
    jobs,
    profiles,
    results,
    review,
)
from app.core.auth import require_unlocked

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_unlocked)])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(documents.router)
api_router.include_router(results.router)
api_router.include_router(review.router)
api_router.include_router(biomarkers.router)
api_router.include_router(jobs.router)
api_router.include_router(export.router)
