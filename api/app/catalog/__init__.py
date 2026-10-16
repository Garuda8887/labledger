"""Catalog, units and ranges: a pure library.

Import surface for the API and extraction layers. No routers here.
"""
from app.catalog.conversions import (
    ConversionUnsupported,
    convert,
    convert_to_canonical,
    load_conversion_table,
)
from app.catalog.crosschecks import run_crosschecks
from app.catalog.flags import check_plausibility, compute_flag, printed_flag_mismatch
from app.catalog.matching import BiomarkerIndex, FUZZY_THRESHOLD, normalize_name
from app.catalog.normalize import NormalizeContext, normalize_row, normalize_rows
from app.catalog.ranges import parse_reference_range
from app.catalog.seed_loader import build_normalize_context, seed_catalog
from app.catalog.units import normalize_unit

__all__ = [
    "BiomarkerIndex",
    "ConversionUnsupported",
    "FUZZY_THRESHOLD",
    "NormalizeContext",
    "build_normalize_context",
    "check_plausibility",
    "compute_flag",
    "convert",
    "convert_to_canonical",
    "load_conversion_table",
    "normalize_name",
    "normalize_row",
    "normalize_rows",
    "normalize_unit",
    "parse_reference_range",
    "printed_flag_mismatch",
    "run_crosschecks",
    "seed_catalog",
]
