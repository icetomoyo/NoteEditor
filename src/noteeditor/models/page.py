"""Data models for page rendering results."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box in pixel coordinates."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class EmbeddedResource:
    """An image resource embedded in a PDF page."""

    index: int
    bbox: BoundingBox
    image: np.ndarray
    width_px: int
    height_px: int

    def __repr__(self) -> str:
        return (
            f"EmbeddedResource(index={self.index}, "
            f"size={self.width_px}x{self.height_px}, "
            f"bbox={self.bbox})"
        )


@dataclass(frozen=True)
class PageMetadata:
    """Metadata for a PDF page (lightweight, without pixel data)."""

    page_number: int
    width_px: int
    height_px: int
    aspect_ratio: float
    total_pages: int


@dataclass(frozen=True)
class PageImage:
    """Rendering result of a single PDF page."""

    page_number: int
    width_px: int
    height_px: int
    dpi: int
    aspect_ratio: float
    image: np.ndarray
    embedded_images: tuple[EmbeddedResource, ...] = ()

    def __repr__(self) -> str:
        return (
            f"PageImage(page={self.page_number}, "
            f"size={self.width_px}x{self.height_px}, "
            f"dpi={self.dpi}, "
            f"resources={len(self.embedded_images)})"
        )
