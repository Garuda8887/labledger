"""Image preprocessing with OpenCV headless: EXIF, deskew, perspective, denoise, contrast, upscale."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

# Target long-edge for OCR (sensible DPI-ish resolution)
TARGET_LONG_EDGE = 2000


def _load_pil(path: Path) -> Image.Image:
    img = Image.open(path)
    # HEIC may need pillow-heif registered; fall back gracefully
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    return img


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    arr = np.array(img)
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def fix_orientation_from_path(path: Path | str) -> np.ndarray:
    """Load image with EXIF orientation applied; return BGR ndarray."""
    return pil_to_bgr(_load_pil(Path(path)))


def upscale_to_long_edge(bgr: np.ndarray, long_edge: int = TARGET_LONG_EDGE) -> np.ndarray:
    h, w = bgr.shape[:2]
    m = max(h, w)
    if m >= long_edge or m == 0:
        return bgr
    scale = long_edge / m
    return cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def estimate_skew_angle(gray: np.ndarray) -> float:
    """Estimate skew angle in degrees using min-area rect on thresholded text."""
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr > 0))
    if coords.shape[0] < 100:
        return 0.0
    rect = cv2.minAreaRect(coords)
    angle = rect[-1]
    # OpenCV returns [-90, 0); normalize to small deskew range
    if angle < -45:
        angle = 90 + angle
    # minAreaRect uses (y,x) from where(); swap sense
    if abs(angle) > 15:
        return 0.0  # refuse large rotations — likely wrong detection
    return float(angle)


def deskew(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    angle = estimate_skew_angle(gray)
    if abs(angle) < 0.3:
        return bgr
    h, w = bgr.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(bgr, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _order_points(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def perspective_correct(bgr: np.ndarray) -> np.ndarray:
    """Try to find a large document quadrilateral and warp; no-op if not found."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blur, 50, 150)
    cnts, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:8]
    page_cnt = None
    for c in cnts:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > 0.4 * h * w:
            page_cnt = approx.reshape(4, 2).astype("float32")
            break
    if page_cnt is None:
        return bgr
    rect = _order_points(page_cnt)
    (tl, tr, br, bl) = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_w = int(max(width_a, width_b))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_h = int(max(height_a, height_b))
    if max_w < 50 or max_h < 50:
        return bgr
    dst = np.array(
        [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
        dtype="float32",
    )
    m = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(bgr, m, (max_w, max_h))


def denoise_and_contrast(bgr: np.ndarray) -> np.ndarray:
    den = cv2.fastNlMeansDenoisingColored(bgr, None, 6, 6, 7, 21)
    lab = cv2.cvtColor(den, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l2, a, b]), cv2.COLOR_LAB2BGR)


def preprocess_image(
    path: Path | str,
    *,
    do_perspective: bool = True,
    do_deskew: bool = True,
    do_denoise: bool = True,
    upscale: bool = True,
) -> np.ndarray:
    """Full phone-photo preprocess pipeline → BGR ndarray ready for OCR."""
    bgr = fix_orientation_from_path(path)
    if upscale:
        bgr = upscale_to_long_edge(bgr)
    if do_perspective:
        bgr = perspective_correct(bgr)
    if do_deskew:
        bgr = deskew(bgr)
    if do_denoise:
        bgr = denoise_and_contrast(bgr)
    return bgr


def preprocess_bgr(
    bgr: np.ndarray,
    *,
    do_perspective: bool = False,
    do_deskew: bool = True,
    do_denoise: bool = True,
    upscale: bool = True,
) -> np.ndarray:
    """Preprocess an already-loaded BGR image (e.g. PDF page render)."""
    if upscale:
        bgr = upscale_to_long_edge(bgr)
    if do_perspective:
        bgr = perspective_correct(bgr)
    if do_deskew:
        bgr = deskew(bgr)
    if do_denoise:
        bgr = denoise_and_contrast(bgr)
    return bgr


def register_heif_opener() -> bool:
    """Optionally register pillow-heif. Returns True if available."""
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
        return True
    except ImportError:
        return False
