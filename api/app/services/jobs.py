"""In-process SQLite-backed job worker (no Redis/Celery)."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_utils import log_event
from app.db import session as db_session
from app.models import Job

JobHandler = Callable[[Job, Session], None]

_handlers: dict[str, JobHandler] = {}
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_lock = threading.Lock()


def register_handler(job_type: str, handler: JobHandler) -> None:
    _handlers[job_type] = handler


def enqueue_job(
    db: Session,
    *,
    job_type: str,
    payload: dict[str, Any] | None = None,
) -> Job:
    job = Job(
        type=job_type,
        status="queued",
        payload=payload or {},
        progress=0.0,
    )
    db.add(job)
    db.flush()
    log_event("job_enqueued", job_id=job.id, job_type=job_type)
    return job


def get_job(db: Session, job_id: str) -> Job | None:
    return db.get(Job, job_id)


def _handle_extract_document(job: Job, db: Session) -> None:
    from app.extraction.pipeline import process_document

    document_id = (job.payload or {}).get("document_id")
    if not document_id:
        raise ValueError("extract_document job missing document_id")
    job.progress = 0.1
    db.add(job)
    db.commit()
    process_document(document_id, db=db)
    job.progress = 1.0


def _ensure_default_handlers() -> None:
    if "extract_document" not in _handlers:
        register_handler("extract_document", _handle_extract_document)


def _process_one(db: Session) -> bool:
    """Claim and run one queued job. Returns True if a job was processed."""
    job = (
        db.query(Job)
        .filter(Job.status == "queued")
        .order_by(Job.created_at.asc())
        .first()
    )
    if job is None:
        return False

    handler = _handlers.get(job.type)
    if handler is None:
        job.status = "failed"
        job.error = f"No handler for job type: {job.type}"
        job.updated_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        log_event("job_failed", job_id=job.id, job_type=job.type)
        return True

    job.status = "running"
    job.updated_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()
    log_event("job_running", job_id=job.id, job_type=job.type)

    try:
        handler(job, db)
        job.status = "succeeded"
        job.progress = 1.0
        job.error = None
        job.updated_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()
        log_event("job_succeeded", job_id=job.id, job_type=job.type)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        # Re-fetch in fresh state
        job = db.get(Job, job.id)
        if job is not None:
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.updated_at = datetime.now(timezone.utc)
            db.add(job)
            db.commit()
        log_event("job_failed", job_id=job.id if job else None, job_type=job.type if job else None)
    return True


def worker_loop(stop_event: threading.Event | None = None) -> None:
    stop = stop_event or _stop_event
    _ensure_default_handlers()
    while not stop.is_set():
        processed = False
        db = db_session.SessionLocal()
        try:
            processed = _process_one(db)
        except Exception:  # noqa: BLE001
            db.rollback()
            log_event("job_worker_error")
        finally:
            db.close()
        if not processed:
            stop.wait(settings.job_poll_interval_sec)


def start_worker() -> None:
    """Start the background worker thread (idempotent)."""
    global _worker_thread
    with _lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _stop_event.clear()
        _ensure_default_handlers()
        _worker_thread = threading.Thread(
            target=worker_loop,
            name="labledger-job-worker",
            daemon=True,
        )
        _worker_thread.start()
        log_event("job_worker_started")


def stop_worker(timeout: float = 2.0) -> None:
    global _worker_thread
    with _lock:
        _stop_event.set()
        t = _worker_thread
        _worker_thread = None
    if t is not None:
        t.join(timeout=timeout)
        log_event("job_worker_stopped")


def run_pending_jobs_once(db: Session | None = None) -> int:
    """Synchronously drain queued jobs (useful in tests). Returns count processed."""
    _ensure_default_handlers()
    own = db is None
    session = db or db_session.SessionLocal()
    count = 0
    try:
        while _process_one(session):
            count += 1
    finally:
        if own:
            session.close()
    return count
