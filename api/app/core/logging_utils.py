"""Logging helpers — never log PHI (result values/names); IDs only."""
from __future__ import annotations

import logging

logger = logging.getLogger("labledger")


def log_event(event: str, **ids: str | int | float | None) -> None:
    """Log an event with ID fields only (no names, values, or PHI)."""
    parts = [f"event={event}"]
    for key, val in ids.items():
        if val is None:
            continue
        parts.append(f"{key}={val}")
    logger.info(" ".join(parts))
