"""Extractor plugin interface. Off by default."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

import numpy as np

from app.schemas.extractor import ExtractorRow
from app.extraction.types import PageContent


class Extractor(ABC):
    """Optional pluggable extractor. Output always goes through normalize + review."""

    name: str = "base"

    @abstractmethod
    def extract_from_page(
        self,
        page: PageContent,
        *,
        image_bgr: np.ndarray | None = None,
    ) -> Sequence[ExtractorRow]:
        """Return candidate rows for one page. Never auto-confirmed."""
