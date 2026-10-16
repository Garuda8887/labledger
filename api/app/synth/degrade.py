"""Degrade digital PDF pages into realistic phone/scan variants. Memory-conscious."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import fitz
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


DEGRADATIONS = (
    "rotation_p5",
    "rotation_m5",
    "perspective",
    "blur",
    "noise",
    "low_light",
    "jpeg",
    "shadow",
    "crop_margin",
)


def pdf_to_page_images(pdf_path: Path, dpi: int = 150) -> list[np.ndarray]:
    """Render PDF pages to BGR arrays at moderate DPI (memory-friendly)."""
    pages: list[np.ndarray] = []
    with fitz.open(pdf_path) as doc:
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=mat, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            # RGB → BGR for OpenCV
            pages.append(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            del pix
    return pages


def _to_pil(bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def _from_pil(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def apply_degradation(bgr: np.ndarray, kind: str, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng(42)
    h, w = bgr.shape[:2]

    if kind == "rotation_p5":
        M = cv2.getRotationMatrix2D((w / 2, h / 2), 5.0, 1.0)
        return cv2.warpAffine(bgr, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    if kind == "rotation_m5":
        M = cv2.getRotationMatrix2D((w / 2, h / 2), -5.0, 1.0)
        return cv2.warpAffine(bgr, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    if kind == "perspective":
        margin = int(min(w, h) * 0.04)
        src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
        dst = np.float32(
            [
                [margin, margin // 2],
                [w - 1 - margin // 2, margin],
                [w - 1 - margin, h - 1 - margin // 2],
                [margin // 2, h - 1 - margin],
            ]
        )
        M = cv2.getPerspectiveTransform(src, dst)
        return cv2.warpPerspective(bgr, M, (w, h), borderValue=(240, 240, 240))
    if kind == "blur":
        return cv2.GaussianBlur(bgr, (5, 5), 1.2)
    if kind == "noise":
        noise = rng.normal(0, 12, bgr.shape).astype(np.float32)
        out = np.clip(bgr.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return out
    if kind == "low_light":
        pil = _to_pil(bgr)
        pil = ImageEnhance.Brightness(pil).enhance(0.55)
        pil = ImageEnhance.Contrast(pil).enhance(0.85)
        return _from_pil(pil)
    if kind == "jpeg":
        pil = _to_pil(bgr)
        buf = io.BytesIO()
        pil.save(buf, format="JPEG", quality=28)
        buf.seek(0)
        return _from_pil(Image.open(buf))
    if kind == "shadow":
        overlay = bgr.copy().astype(np.float32)
        # Diagonal soft shadow
        yy, xx = np.mgrid[0:h, 0:w]
        shade = 0.45 + 0.55 * ((xx + yy) / (w + h))
        overlay *= shade[..., None]
        return np.clip(overlay, 0, 255).astype(np.uint8)
    if kind == "crop_margin":
        cut = int(min(w, h) * 0.06)
        cropped = bgr[cut : h - cut, cut : w - cut]
        return cv2.copyMakeBorder(cropped, cut, cut, cut, cut, cv2.BORDER_CONSTANT, value=(230, 230, 230))
    raise ValueError(f"Unknown degradation: {kind}")


def save_image(bgr: np.ndarray, path: Path, *, jpeg_quality: int = 85) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        cv2.imwrite(str(path), bgr, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    else:
        cv2.imwrite(str(path), bgr)


def images_to_scanned_pdf(images: Iterable[np.ndarray], out_path: Path, dpi: int = 150) -> None:
    """Pack BGR page images into a scanned-like PDF (embedded JPEGs)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    try:
        for bgr in images:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=75)
            jpeg_bytes = buf.getvalue()
            h, w = bgr.shape[:2]
            # Page size in points
            rect = fitz.Rect(0, 0, w * 72 / dpi, h * 72 / dpi)
            page = doc.new_page(width=rect.width, height=rect.height)
            page.insert_image(rect, stream=jpeg_bytes)
        doc.save(out_path)
    finally:
        doc.close()


def degrade_pdf(
    pdf_path: Path,
    out_dir: Path,
    *,
    kinds: Sequence[str] | None = None,
    stem: str | None = None,
    dpi: int = 150,
    multi_photo: bool = False,
) -> dict[str, list[Path]]:
    """Create degraded image (+ scanned PDF) variants for one digital PDF.

    Returns mapping degradation_kind → list of output paths.
    Processes one kind at a time to limit peak memory.
    """

    kinds = list(kinds or DEGRADATIONS)
    stem = stem or Path(pdf_path).stem
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = pdf_to_page_images(pdf_path, dpi=dpi)
    results: dict[str, list[Path]] = {}
    rng = np.random.default_rng(abs(hash(stem)) % (2**32))

    for kind in kinds:
        paths: list[Path] = []
        degraded_pages = [apply_degradation(p, kind, rng) for p in pages]
        # Save first page as image (always)
        img_path = out_dir / f"{stem}__{kind}.jpg"
        save_image(degraded_pages[0], img_path)
        paths.append(img_path)
        # Scanned PDF of all pages
        pdf_out = out_dir / f"{stem}__{kind}.pdf"
        images_to_scanned_pdf(degraded_pages, pdf_out, dpi=dpi)
        paths.append(pdf_out)
        results[kind] = paths
        del degraded_pages

    if multi_photo and pages:
        # Split first page into overlapping photo-like crops (multi-photo set)
        p0 = pages[0]
        h, w = p0.shape[:2]
        crops = [
            ("top", p0[0 : int(h * 0.55), :]),
            ("mid", p0[int(h * 0.30) : int(h * 0.85), :]),
            ("bot", p0[int(h * 0.50) :, :]),
        ]
        photo_paths: list[Path] = []
        for name, crop in crops:
            warped = apply_degradation(crop, "perspective", rng)
            path = out_dir / f"{stem}__multiphoto_{name}.jpg"
            save_image(warped, path)
            photo_paths.append(path)
        results["multiphoto"] = photo_paths

    del pages
    return results
