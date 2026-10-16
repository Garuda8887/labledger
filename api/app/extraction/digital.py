"""Digital PDF text extraction via pdfplumber + PyMuPDF with word boxes."""
from __future__ import annotations

from pathlib import Path

import fitz
import pdfplumber

from app.extraction.types import PageContent, WordBox


def _words_from_pymupdf(page: fitz.Page, page_number: int) -> list[WordBox]:
    # words: (x0, y0, x1, y1, "word", block, line, word_no)
    raw = page.get_text("words") or []
    out: list[WordBox] = []
    for w in raw:
        text = (w[4] or "").strip()
        if not text:
            continue
        out.append(
            WordBox(
                text=text,
                x0=float(w[0]),
                y0=float(w[1]),
                x1=float(w[2]),
                y1=float(w[3]),
                conf=1.0,
            )
        )
    return out


def _words_from_pdfplumber(page: pdfplumber.page.Page) -> list[WordBox]:
    words = page.extract_words(
        keep_blank_chars=False,
        use_text_flow=False,
        extra_attrs=["fontname", "size"],
    ) or []
    out: list[WordBox] = []
    for w in words:
        text = (w.get("text") or "").strip()
        if not text:
            continue
        out.append(
            WordBox(
                text=text,
                x0=float(w["x0"]),
                y0=float(w["top"]),
                x1=float(w["x1"]),
                y1=float(w["bottom"]),
                conf=1.0,
            )
        )
    return out


def extract_digital_page_pymupdf(doc: fitz.Document, page_index: int) -> PageContent:
    page = doc[page_index]
    rect = page.rect
    return PageContent(
        page_number=page_index + 1,
        kind="digital",
        words=_words_from_pymupdf(page, page_index + 1),
        width=float(rect.width),
        height=float(rect.height),
    )


def extract_digital_pdf(path: Path | str, *, prefer: str = "pymupdf") -> list[PageContent]:
    """Extract per-page words from a digital PDF.

    prefer: 'pymupdf' (default, fast) or 'pdfplumber' (sometimes better tables).
    Falls back to the other if the preferred engine yields too few words.
    """
    path = Path(path)
    pages: list[PageContent] = []

    with fitz.open(path) as doc:
        for i in range(doc.page_count):
            pc = extract_digital_page_pymupdf(doc, i)
            pages.append(pc)

    if prefer == "pdfplumber" or any(len(p.words) < 8 for p in pages):
        plumber_pages: list[PageContent] = []
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                words = _words_from_pdfplumber(page)
                existing = pages[i] if i < len(pages) else None
                # Prefer whichever has more words
                if existing is None or len(words) > len(existing.words):
                    plumber_pages.append(
                        PageContent(
                            page_number=i + 1,
                            kind="digital",
                            words=words,
                            width=float(page.width or 0),
                            height=float(page.height or 0),
                        )
                    )
                else:
                    plumber_pages.append(existing)
        pages = plumber_pages

    return pages


def render_pdf_page_bgr(path: Path | str, page_index: int, *, dpi: int = 200):
    """Render a PDF page to a BGR numpy array for OCR fallback."""
    import numpy as np

    path = Path(path)
    with fitz.open(path) as doc:
        page = doc[page_index]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        # PyMuPDF is RGB
        import cv2

        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR), float(pix.width), float(pix.height)


PAGE_RASTER_DPI = 150


def render_pdf_pages_to_dir(
    path: Path | str,
    out_dir: Path | str,
    *,
    dpi: int = PAGE_RASTER_DPI,
    max_pages: int | None = None,
    overwrite: bool = False,
) -> int:
    """Render PDF pages to ``out_dir/{n}.png`` (1-indexed). Returns total PDF page count.

    Used for the review UI / ``GET /documents/{id}/pages/{n}``. Existing PNGs are kept
    unless ``overwrite``.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    with fitz.open(Path(path)) as doc:
        n = doc.page_count
        limit = n if max_pages is None else min(n, max_pages)
        for i in range(limit):
            dest = out / f"{i + 1}.png"
            if dest.exists() and not overwrite:
                continue
            pix = doc[i].get_pixmap(matrix=mat, alpha=False)
            tmp = dest.with_suffix(".png.tmp")
            tmp.write_bytes(pix.tobytes("png"))
            tmp.replace(dest)
        return n
