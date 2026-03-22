"""Data models for layout detection results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from noteeditor.models.page import BoundingBox


class RegionLabel(StrEnum):
    """Semantic label for a detected layout region."""

    TITLE = "title"
    BODY_TEXT = "body_text"
    IMAGE = "image"
    TABLE = "table"
    HEADER = "header"
    FOOTER = "footer"
    FIGURE_CAPTION = "figure_caption"
    EQUATION = "equation"
    CODE_BLOCK = "code_block"
    REFERENCE = "reference"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LayoutRegion:
    """A single detected region within a page layout."""

    bbox: BoundingBox
    label: RegionLabel
    confidence: float
    region_id: str


@dataclass(frozen=True)
class LayoutResult:
    """Layout detection result for a single page."""

    page_number: int
    regions: tuple[LayoutRegion, ...]
