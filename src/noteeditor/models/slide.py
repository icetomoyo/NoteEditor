"""Data models for slide content assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from noteeditor.models.content import FontMatch
from noteeditor.models.page import BoundingBox


@dataclass(frozen=True)
class TextBlock:
    """A text block to be placed on a slide."""

    region_id: str
    bbox: BoundingBox
    text: str
    font_match: FontMatch
    is_formula: bool
    formula_latex: str | None = None


@dataclass(frozen=True)
class ImageBlock:
    """An image block to be placed on a slide."""

    region_id: str
    bbox: BoundingBox
    image: np.ndarray
    source: Literal["embedded", "cropped"]

    def __repr__(self) -> str:
        return (
            f"ImageBlock(region_id={self.region_id!r}, "
            f"source={self.source!r})"
        )


@dataclass(frozen=True)
class SlideContent:
    """Complete content for a single slide."""

    page_number: int
    background_image: np.ndarray | None
    full_page_image: np.ndarray
    text_blocks: tuple[TextBlock, ...]
    image_blocks: tuple[ImageBlock, ...]
    status: Literal["success", "failed", "fallback"]

    def __repr__(self) -> str:
        return (
            f"SlideContent(page={self.page_number}, "
            f"status={self.status!r}, "
            f"texts={len(self.text_blocks)}, "
            f"images={len(self.image_blocks)})"
        )
