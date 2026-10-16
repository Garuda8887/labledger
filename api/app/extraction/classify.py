"""Classify each page as digital text vs scanned image."""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from app.extraction.types import PageKind


def classify_pdf_page(doc: fitz.Document, page_index: int, *, min_chars: int = 40) -> PageKind:
    """Return 'digital' if the page has a usable text layer, else 'scanned'."""
    page = doc[page_index]
    text = (page.get_text("text") or "").strip()
    # Also check word count via dict to avoid watermark-only pages
    words = page.get_text("words") or []
    if len(text) >= min_chars and len(words) >= 8:
        return "digital"
    return "scanned"


def classify_pdf(path: Path | str) -> list[PageKind]:
    path = Path(path)
    kinds: list[PageKind] = []
    with fitz.open(path) as doc:
        for i in range(doc.page_count):
            kinds.append(classify_pdf_page(doc, i))
    return kinds


def classify_source(path: Path | str, mime: str) -> tuple[str, list[PageKind]]:
    """Return (source_type hint, per-page kinds).

    source_type is one of digital_pdf|scanned_pdf|image (multi_image is caller concern).
    """
    path = Path(path)
    if mime == "application/pdf" or path.suffix.lower() == ".pdf":
        kinds = classify_pdf(path)
        if kinds and all(k == "digital" for k in kinds):
            return "digital_pdf", kinds
        if kinds and all(k == "scanned" for k in kinds):
            return "scanned_pdf", kinds
        # Mixed: treat as scanned_pdf if any scanned, else digital
        if any(k == "scanned" for k in kinds):
            return "scanned_pdf", kinds
        return "digital_pdf", kinds
    return "image", ["scanned"]
