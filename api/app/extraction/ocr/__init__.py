"""OCR adapters. Default: Tesseract. PaddleOCR is a selectable stub, not installed."""
from __future__ import annotations

import os

from app.extraction.ocr.base import OcrAdapter
from app.extraction.ocr.tesseract_adapter import TesseractAdapter


def get_ocr_adapter(engine: str | None = None) -> OcrAdapter:
    name = (engine or os.environ.get("OCR_ENGINE") or "tesseract").strip().lower()
    if name in ("paddle", "paddleocr"):
        from app.extraction.ocr.paddle_stub import PaddleOcrStub

        return PaddleOcrStub()
    return TesseractAdapter()


__all__ = ["OcrAdapter", "TesseractAdapter", "get_ocr_adapter"]
