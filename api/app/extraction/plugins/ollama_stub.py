"""Ollama vision-model reference stub. Disabled unless EXTRACTOR_PLUGIN=ollama."""
from __future__ import annotations

import logging
import os
from typing import Sequence

import numpy as np

from app.extraction.plugins.base import Extractor
from app.extraction.types import PageContent
from app.schemas.extractor import ExtractorRow

logger = logging.getLogger(__name__)


class OllamaExtractor(Extractor):
    """Reference plugin that would call a local Ollama vision model.

    This stub does NOT make network calls. When enabled it returns no rows
    and logs that the real adapter is not wired.
    Configure via:
      EXTRACTOR_PLUGIN=ollama
      OLLAMA_URL=http://127.0.0.1:11434  (unused in stub)
      OLLAMA_MODEL=llava                  (unused in stub)
    """

    name = "ollama"

    def __init__(self) -> None:
        self.url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "llava")

    def extract_from_page(
        self,
        page: PageContent,
        *,
        image_bgr: np.ndarray | None = None,
    ) -> Sequence[ExtractorRow]:
        logger.info(
            "Ollama extractor stub active (url=%s model=%s page=%s); returning no rows",
            self.url,
            self.model,
            page.page_number,
        )
        # Intentionally empty — a future implementation would POST the image to Ollama
        # and map JSON into ExtractorRow with source="plugin".
        return []
