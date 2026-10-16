"""Job status polling + optional SSE progress stream."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import session as db_session
from app.db.session import get_db
from app.models import Job
from app.schemas.job import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"detail": "Job not found", "code": "not_found"})
    return job


@router.get("/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    """SSE stream of job progress until terminal state."""

    async def event_gen():
        while True:
            if await request.is_disconnected():
                break
            db = db_session.SessionLocal()
            try:
                job = db.get(Job, job_id)
                if job is None:
                    yield f"event: error\ndata: {json.dumps({'code': 'not_found'})}\n\n"
                    break
                payload = {
                    "id": job.id,
                    "status": job.status,
                    "progress": job.progress,
                    "error": job.error,
                }
                yield f"event: status\ndata: {json.dumps(payload)}\n\n"
                if job.status in ("succeeded", "failed", "cancelled"):
                    break
            finally:
                db.close()
            await asyncio.sleep(0.5)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
