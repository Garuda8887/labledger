"""Document upload, list, detail, status, page images."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.logging_utils import log_event
from app.db.session import get_db
from app.models import Document, Job, Profile
from app.schemas.document import (
    DocumentListResponse,
    DocumentRead,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.schemas.job import JobRead
from app.services import storage
from app.services.jobs import enqueue_job

router = APIRouter(tags=["documents"])


def _doc_read(doc: Document, job_id: str | None = None) -> DocumentRead:
    data = DocumentRead.model_validate(doc)
    if job_id:
        data = data.model_copy(update={"job_id": job_id})
    return data


@router.post(
    "/profiles/{profile_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_documents(
    profile_id: str,
    files: list[UploadFile] = File(...),
    multi_page: bool = Form(False),
    allow_duplicate: bool = Form(False),
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Multi-file upload. Returns immediately with documents in `processing`
    and queued extract jobs. Set multi_page=true to merge image files into
    one multi_image Document.
    """
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})
    if not files:
        raise HTTPException(status_code=400, detail={"detail": "No files provided", "code": "no_files"})

    # Read all uploads first
    payloads: list[tuple[str, bytes, str | None]] = []
    for f in files:
        data = await f.read()
        name = f.filename or "upload.bin"
        try:
            storage.validate_upload(name, len(data))
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"detail": str(exc), "code": "invalid_upload"},
            ) from exc
        payloads.append((name, data, f.content_type))

    documents: list[Document] = []
    jobs: list[Job] = []
    duplicates: list[dict] = []

    def _create_one(
        name: str,
        data: bytes,
        content_type: str | None,
        *,
        source_type: str | None = None,
        page_count: int = 1,
        extra_pages: list[tuple[str, bytes]] | None = None,
    ) -> Document | None:
        digest = storage.sha256_bytes(data)
        existing = (
            db.query(Document)
            .filter(Document.profile_id == profile_id, Document.sha256 == digest)
            .first()
        )
        if existing and not allow_duplicate:
            duplicates.append(
                {
                    "filename": name,
                    "sha256": digest,
                    "existing_document_id": existing.id,
                    "code": "duplicate",
                }
            )
            return None

        mime = storage.guess_mime(name, content_type)
        st = source_type or storage.infer_source_type(name)
        rel = storage.store_original(profile_id, digest, name, data)

        # Seed page images for image uploads so page endpoint works immediately
        ext = Path(name).suffix.lower()
        if ext in storage.IMAGE_EXTENSIONS:
            storage.store_page_image(profile_id, digest, 1, data, ext=ext if ext != ".jpeg" else ".jpg")
        elif ext == ".pdf":
            # Early page-1 thumbnail + true page_count (fast; full set rendered by job)
            try:
                from app.extraction.digital import render_pdf_pages_to_dir

                page_count = render_pdf_pages_to_dir(
                    storage.resolve_stored_path(str(rel)),
                    storage.pages_dir(profile_id, digest),
                    max_pages=1,
                )
            except Exception:  # noqa: BLE001 — job renders again
                pass
        if extra_pages:
            for idx, (pname, pdata) in enumerate(extra_pages, start=2):
                pext = Path(pname).suffix.lower() or ".png"
                if pext == ".jpeg":
                    pext = ".jpg"
                storage.store_page_image(profile_id, digest, idx, pdata, ext=pext)

        # Unique sha override when allow_duplicate and collision
        sha_store = digest
        if existing and allow_duplicate:
            import uuid

            sha_store = f"{digest}-{uuid.uuid4().hex[:8]}"
            rel = storage.store_original(profile_id, sha_store, name, data)
            if ext in storage.IMAGE_EXTENSIONS:
                storage.store_page_image(
                    profile_id, sha_store, 1, data, ext=ext if ext != ".jpeg" else ".jpg"
                )

        doc = Document(
            profile_id=profile_id,
            original_filename=name,
            sha256=sha_store if (existing and allow_duplicate) else digest,
            mime=mime,
            stored_path=str(rel),
            source_type=st,
            page_count=page_count,
            status="processing",
        )
        db.add(doc)
        db.flush()
        job = enqueue_job(db, job_type="extract_document", payload={"document_id": doc.id})
        documents.append(doc)
        jobs.append(job)
        log_event("document_uploaded", document_id=doc.id, profile_id=profile_id, job_id=job.id)
        return doc

    if multi_page and len(payloads) > 1:
        # All must be images
        for name, _, _ in payloads:
            if Path(name).suffix.lower() not in storage.IMAGE_EXTENSIONS:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "detail": "multi_page merge requires image files only",
                        "code": "invalid_upload",
                    },
                )
        first_name, first_data, first_ct = payloads[0]
        extras = [(n, d) for n, d, _ in payloads[1:]]
        _create_one(
            first_name,
            first_data,
            first_ct,
            source_type="multi_image",
            page_count=len(payloads),
            extra_pages=extras,
        )
    else:
        for name, data, ct in payloads:
            _create_one(name, data, ct)

    db.commit()
    for d in documents:
        db.refresh(d)
    for j in jobs:
        db.refresh(j)

    job_by_doc = {(j.payload or {}).get("document_id"): j.id for j in jobs}
    return DocumentUploadResponse(
        documents=[_doc_read(d, job_by_doc.get(d.id)) for d in documents],
        jobs=[JobRead.model_validate(j) for j in jobs],
        duplicates=duplicates,
    )


@router.get("/profiles/{profile_id}/documents", response_model=DocumentListResponse)
def list_documents(
    profile_id: str,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> DocumentListResponse:
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail={"detail": "Profile not found", "code": "not_found"})
    q = db.query(Document).filter(Document.profile_id == profile_id)
    if status_filter:
        q = q.filter(Document.status == status_filter)
    items = q.order_by(Document.uploaded_at.desc()).all()
    return DocumentListResponse(items=[DocumentRead.model_validate(d) for d in items], total=len(items))


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"detail": "Document not found", "code": "not_found"})
    return doc


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
def document_status(document_id: str, db: Session = Depends(get_db)) -> DocumentStatusResponse:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"detail": "Document not found", "code": "not_found"})
    job = (
        db.query(Job)
        .filter(Job.type == "extract_document")
        .order_by(Job.created_at.desc())
        .all()
    )
    matched = None
    for j in job:
        if (j.payload or {}).get("document_id") == document_id:
            matched = j
            break
    return DocumentStatusResponse(
        id=doc.id,
        status=doc.status,
        page_count=doc.page_count,
        job=JobRead.model_validate(matched) if matched else None,
    )


@router.get("/documents/{document_id}/pages/{page}")
def get_page_image(document_id: str, page: int, db: Session = Depends(get_db)) -> FileResponse:
    """Serve a stored page image (stub for PDF render — B fills pages/)."""
    if page < 1:
        raise HTTPException(status_code=400, detail={"detail": "page must be >= 1", "code": "invalid_page"})
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail={"detail": "Document not found", "code": "not_found"})

    # Prefer pages/ directory (folder named by document.sha256)
    path = storage.page_image_path(doc.profile_id, doc.sha256, page)

    if path is None:
        # Fallback: if original is an image and page==1, serve original
        orig = storage.resolve_stored_path(doc.stored_path)
        if page == 1 and orig.exists() and doc.mime.startswith("image/"):
            path = orig

    if path is None or not path.exists():
        raise HTTPException(
            status_code=404,
            detail={
                "detail": "Page image not available yet",
                "code": "page_not_ready",
            },
        )

    media = storage.guess_mime(path.name)
    return FileResponse(path, media_type=media, filename=path.name)
