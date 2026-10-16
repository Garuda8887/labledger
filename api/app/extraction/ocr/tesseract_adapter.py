"""Tesseract OCR adapter (default, required)."""
from __future__ import annotations

import logging

import cv2
import numpy as np
import pytesseract
from pytesseract import Output

from app.extraction.ocr.base import OcrAdapter
from app.extraction.types import WordBox

logger = logging.getLogger(__name__)


class TesseractAdapter(OcrAdapter):
    name = "tesseract"

    def __init__(self, *, lang: str = "eng", psm: int = 6, oem: int = 3) -> None:
        self.lang = lang
        self.psm = psm
        self.oem = oem

    def extract_words(self, image_bgr: np.ndarray) -> list[WordBox]:
        if image_bgr is None or image_bgr.size == 0:
            return []
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
        config = f"--oem {self.oem} --psm {self.psm}"
        try:
            data = pytesseract.image_to_data(gray, lang=self.lang, config=config, output_type=Output.DICT)
        except pytesseract.TesseractNotFoundError:
            logger.error("tesseract binary not found on PATH")
            raise
        words: list[WordBox] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            conf_raw = data["conf"][i]
            try:
                conf = float(conf_raw)
            except (TypeError, ValueError):
                conf = -1.0
            if conf < 0:
                continue
            x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
            words.append(
                WordBox(
                    text=text,
                    x0=float(x),
                    y0=float(y),
                    x1=float(x + w),
                    y1=float(y + h),
                    conf=max(0.0, min(1.0, conf / 100.0)),
                )
            )
        return words
