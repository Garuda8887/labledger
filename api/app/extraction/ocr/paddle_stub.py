"""PaddleOCR adapter stub — NOT installed / OFF by default (RAM-heavy).

Do not import paddleocr. Selection is via OCR_ENGINE=paddle, but this stub
raises until an optional image with PaddleOCR is built.
"""
from __future__ import annotations

import numpy as np

from app.extraction.ocr.base import OcrAdapter
from app.extraction.types import WordBox


class PaddleOcrStub(OcrAdapter):
    name = "paddle"

    def extract_words(self, image_bgr: np.ndarray) -> list[WordBox]:
        raise RuntimeError(
            "PaddleOCR is not installed in this build. "
            "Use OCR_ENGINE=tesseract (default) or rebuild with OCR_ENGINE=paddle "
            "when a larger image is available. Paddle is intentionally skipped by default."
        )
