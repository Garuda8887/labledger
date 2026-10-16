"""Ingest helpers: accept PDF/JPG/PNG/HEIC/WEBP; sha256 dedupe; store under data/files.

Supports both layouts:
  simple:  data/files/<profile>/<sha><ext>
  nested:  data/files/<profile>/<sha>/original/<filename>

Prefers A's nested layout when `app.services.storage` is importable; otherwise
writes the simple path so this module works standalone.
"""
from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff"}
MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}
MAX_BYTES_DEFAULT = 50 * 1024 * 1024


class IngestError(ValueError):
    pass


@dataclass
class IngestResult:
    sha256: str
    mime: str
    stored_path: str  # relative to data dir preferred
    relative_path: str
    original_filename: str
    size_bytes: int
    deduplicated: bool


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def files_root() -> Path:
    root = settings.labledger_data_dir / "files"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _max_bytes() -> int:
    return int(getattr(settings, "max_upload_bytes", MAX_BYTES_DEFAULT) or MAX_BYTES_DEFAULT)


def _guess_mime(filename: str, content_type: str | None = None) -> str:
    ext = Path(filename).suffix.lower()
    if content_type and content_type != "application/octet-stream":
        return content_type.split(";")[0].strip().lower()
    if ext in MIME_BY_EXT:
        return MIME_BY_EXT[ext]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _store_via_a(
    profile_id: str,
    data: bytes,
    original_filename: str,
    *,
    content_type: str | None,
) -> IngestResult | None:
    try:
        from app.services import storage as a_storage
    except ImportError:
        return None
    try:
        a_storage.validate_upload(original_filename, len(data))
    except ValueError as e:
        raise IngestError(str(e)) from e
    sha = compute_sha256(data)
    mime = a_storage.guess_mime(original_filename, content_type)
    dest_dir = a_storage.document_dir(profile_id, sha)
    orig_dir = dest_dir / "original"
    existing = [p for p in orig_dir.glob("*") if p.is_file()] if orig_dir.exists() else []
    deduped = bool(existing)
    if deduped:
        rel = existing[0].relative_to(settings.labledger_data_dir)
    else:
        rel = a_storage.store_original(profile_id, sha, original_filename, data)
    return IngestResult(
        sha256=sha,
        mime=mime,
        stored_path=str(rel),
        relative_path=str(rel),
        original_filename=original_filename,
        size_bytes=len(data),
        deduplicated=deduped,
    )


def store_bytes(
    profile_id: str,
    data: bytes,
    original_filename: str,
    *,
    content_type: str | None = None,
    allow_override: bool = True,
) -> IngestResult:
    if not data:
        raise IngestError("Empty file")
    if len(data) > _max_bytes():
        raise IngestError(f"File exceeds max size of {_max_bytes()} bytes")
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise IngestError(f"Unsupported extension {ext!r}; allowed: {sorted(ALLOWED_EXTENSIONS)}")

    via_a = _store_via_a(profile_id, data, original_filename, content_type=content_type)
    if via_a is not None:
        return via_a

    # Standalone layout: files/<profile>/<sha><ext>
    sha = compute_sha256(data)
    mime = _guess_mime(original_filename, content_type)
    profile_dir = files_root() / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    dest = profile_dir / f"{sha}{ext}"
    relative = f"files/{profile_id}/{sha}{ext}"
    deduped = dest.exists()
    if not deduped:
        dest.write_bytes(data)
    return IngestResult(
        sha256=sha,
        mime=mime,
        stored_path=relative,
        relative_path=relative,
        original_filename=original_filename,
        size_bytes=len(data),
        deduplicated=deduped,
    )


def store_path(
    profile_id: str,
    path: Path | str,
    *,
    original_filename: str | None = None,
    content_type: str | None = None,
    allow_override: bool = True,
) -> IngestResult:
    p = Path(path)
    return store_bytes(
        profile_id,
        p.read_bytes(),
        original_filename or p.name,
        content_type=content_type,
        allow_override=allow_override,
    )


def resolve_stored_path(stored_path: str) -> Path:
    """Resolve Document.stored_path (A nested, B simple, or absolute)."""
    try:
        from app.services import storage as a_storage

        p = a_storage.resolve_stored_path(stored_path)
        if p.exists():
            return p
    except ImportError:
        pass

    p = Path(stored_path)
    if p.is_absolute() and p.exists():
        return p
    candidate = settings.labledger_data_dir / stored_path
    if candidate.exists():
        return candidate
    # If stored_path points at a sha dir, look for original/*
    if candidate.is_dir():
        originals = list((candidate / "original").glob("*")) if (candidate / "original").exists() else []
        if originals:
            return originals[0]
    raise FileNotFoundError(f"Stored file not found: {stored_path}")
