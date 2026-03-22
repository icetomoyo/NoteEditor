"""Data models for content extraction results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from noteeditor.models.layout import RegionLabel
from noteeditor.models.page import BoundingBox


@dataclass(frozen=True)
class OCRResult:
    """OCR extraction result for a text region."""

    region_id: str
    text: str
    confidence: float
    is_formula: bool
    formula_latex: str | None = None


@dataclass(frozen=True)
class ExtractedImage:
    """An extracted image from a PDF page."""

    region_id: str
    image: np.ndarray
    source: Literal["embedded", "cropped"]
    bbox: BoundingBox
    width_px: int
    height_px: int

    def __repr__(self) -> str:
        return (
            f"ExtractedImage(region_id={self.region_id!r}, "
            f"size={self.width_px}x{self.height_px}, "
            f"source={self.source!r})"
        )


@dataclass(frozen=True)
class FontMatch:
    """Font matching result for a text region."""

    region_id: str
    label: RegionLabel
    font_name: str
    font_path: Path | None
    system_fallback: str | None
    is_fallback: bool
