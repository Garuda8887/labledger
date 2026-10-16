"""Optional Extractor plugins. Off unless EXTRACTOR_PLUGIN is set."""
from __future__ import annotations

import os

from app.extraction.plugins.base import Extractor


def get_extractor_plugin(name: str | None = None) -> Extractor | None:
    plugin = (name if name is not None else os.environ.get("EXTRACTOR_PLUGIN") or "").strip().lower()
    if not plugin or plugin in ("none", "off", "0", "false"):
        return None
    if plugin == "ollama":
        from app.extraction.plugins.ollama_stub import OllamaExtractor

        return OllamaExtractor()
    if plugin == "cloud":
        raise RuntimeError(
            "Cloud extractor stub is disabled by default and sends data off-device. "
            "Do not enable in local-first builds."
        )
    raise ValueError(f"Unknown EXTRACTOR_PLUGIN={plugin!r}")


__all__ = ["Extractor", "get_extractor_plugin"]
