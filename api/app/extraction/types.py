"""Shared types for the extraction pipeline (words, pages, metadata)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class WordBox:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float = 1.0  # 0–1; digital text defaults to 1.0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


PageKind = Literal["digital", "scanned"]


@dataclass
class PageContent:
    page_number: int  # 1-based
    kind: PageKind
    words: list[WordBox] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0
    # Optional rendered/preprocessed image path for review UI later
    image_path: str | None = None


@dataclass
class DocumentMeta:
    lab_name: str | None = None
    report_date: str | None = None  # ISO date YYYY-MM-DD when parsed
    collected_at: str | None = None  # ISO datetime or date
    sample_id: str | None = None
    printed_patient_name: str | None = None
    printed_patient_age: str | None = None
    printed_patient_sex: str | None = None
