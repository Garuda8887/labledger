"""Flag computation helpers. Re-exports + thin wrappers."""
from __future__ import annotations

from app.catalog.ranges import compute_flag, printed_flag_mismatch

__all__ = ["compute_flag", "printed_flag_mismatch", "check_plausibility"]


def check_plausibility(
    value: float | None,
    pmin: float | None,
    pmax: float | None,
) -> str | None:
    """Return 'suspect_unit_or_misread' if outside plausible range."""
    if value is None:
        return None
    if pmin is not None and value < pmin:
        return "suspect_unit_or_misread"
    if pmax is not None and value > pmax:
        return "suspect_unit_or_misread"
    return None
