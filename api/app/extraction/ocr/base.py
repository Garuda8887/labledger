"""OCR adapter interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.extraction.types import WordBox


class OcrAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def extract_words(self, image_bgr: np.ndarray) -> list[WordBox]:
        """Return word boxes with per-word confidence in [0, 1]."""

    def extract_text(self, image_bgr: np.ndarray) -> str:
        words = self.extract_words(image_bgr)
        return " ".join(w.text for w in words)
