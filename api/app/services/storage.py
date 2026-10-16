"""File storage under /data/files/<profile_id>/<sha256>/."""
from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from app.core.config import settings

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".webp",
    ".tif",
    ".tiff",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff"}
MIME_MAP = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".heic": "image/heic",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def guess_mime(filename: str, content_type: str | None = None) -> str:
    ext = Path(filename).suffix.lower()
    if ext in MIME_MAP:
        return MIME_MAP[ext]
    if content_type and content_type != "application/octet-stream":
        return content_type
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def infer_source_type(filename: str, *, multi: bool = False) -> str:
    ext = Path(filename).suffix.lower()
    if multi:
        return "multi_image"
    if ext == ".pdf":
        return "digital_pdf"  # B may reclassify as scanned_pdf
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "image"


def validate_upload(filename: str, size: int) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or '(none)'}")
    if size <= 0:
        raise ValueError("Empty file")
    if size > settings.max_upload_bytes:
        raise ValueError(f"File exceeds max size of {settings.max_upload_bytes} bytes")


def profile_files_dir(profile_id: str) -> Path:
    path = settings.files_dir / profile_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_dir(profile_id: str, sha256: str) -> Path:
    path = profile_files_dir(profile_id) / sha256
    path.mkdir(parents=True, exist_ok=True)
    return path


def pages_dir(profile_id: str, sha256: str) -> Path:
    path = document_dir(profile_id, sha256) / "pages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_original(
    profile_id: str,
    sha256: str,
    filename: str,
    data: bytes,
) -> Path:
    """Write original bytes; return relative path from data dir."""
    dest_dir = document_dir(profile_id, sha256)
    safe_name = Path(filename).name or "upload.bin"
    dest = dest_dir / "original" / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        dest.write_bytes(data)
    # Relative to data dir for portability
    return dest.relative_to(settings.labledger_data_dir)


def store_page_image(
    profile_id: str,
    sha256: str,
    page: int,
    data: bytes,
    ext: str = ".png",
) -> Path:
    dest = pages_dir(profile_id, sha256) / f"{page}{ext}"
    dest.write_bytes(data)
    return dest.relative_to(settings.labledger_data_dir)


def resolve_stored_path(stored_path: str) -> Path:
    """Resolve a stored_path (relative or absolute) under data dir."""
    p = Path(stored_path)
    if p.is_absolute():
        return p
    return settings.labledger_data_dir / p


def page_image_path(profile_id: str, sha256: str, page: int) -> Path | None:
    """Return existing page image path if present."""
    base = pages_dir(profile_id, sha256)
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = base / f"{page}{ext}"
        if candidate.exists():
            return candidate
    return None


def delete_profile_files(profile_id: str) -> None:
    path = settings.files_dir / profile_id
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
