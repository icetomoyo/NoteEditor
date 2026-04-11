"""OCR stage - text extraction via OCR Backend abstraction.

Crops text-type regions from the page image and sends them to
the configured OCR backend (Transformers, Ollama, vLLM, or API).
"""

from __future__ import annotations

import logging

import numpy as np

from noteeditor.infra.ocr_backend import OCRBackend, OCRResponse
from noteeditor.models.content import OCRResult
from noteeditor.models.layout import LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import BoundingBox, PageImage

logger = logging.getLogger(__name__)

_TEXT_LABELS: frozenset[RegionLabel] = frozenset({
    RegionLabel.TITLE,
    RegionLabel.BODY_TEXT,
    RegionLabel.EQUATION,
    RegionLabel.CODE_BLOCK,
})

_CROP_PADDING = 10

# Task prompts for different region types
_TASK_PROMPTS: dict[RegionLabel, str] = {
    RegionLabel.TITLE: "Text Recognition:",
    RegionLabel.BODY_TEXT: "Text Recognition:",
    RegionLabel.EQUATION: "Formula Recognition:",
    RegionLabel.CODE_BLOCK: "Text Recognition:",
}


def _filter_text_regions(
    regions: tuple[LayoutRegion, ...],
) -> tuple[LayoutRegion, ...]:
    """Filter layout regions to text-type only.

    Args:
        regions: All detected layout regions.

    Returns:
        Immutable tuple of regions with text-type labels.
    """
    return tuple(r for r in regions if r.label in _TEXT_LABELS)


def _crop_region(
    image: np.ndarray,
    bbox: BoundingBox,
    padding: int = _CROP_PADDING,
) -> np.ndarray:
    """Crop a region from the page image with padding, clamped to image bounds.

    Args:
        image: Full page image (H, W, 3), dtype uint8.
        bbox: Bounding box of the region to crop.
        padding: Extra pixels around the bbox to prevent text truncation.

    Returns:
        Cropped region image, dtype uint8.
    """
    h, w = image.shape[:2]
    y1 = max(0, int(bbox.y) - padding)
    x1 = max(0, int(bbox.x) - padding)
    y2 = min(h, int(bbox.y + bbox.height) + padding)
    x2 = min(w, int(bbox.x + bbox.width) + padding)
    return image[y1:y2, x1:x2]


def _response_to_result(
    response: OCRResponse,
    region_id: str,
) -> OCRResult:
    """Convert an OCRResponse to an OCRResult with region association."""
    return OCRResult(
        region_id=region_id,
        text=response.text,
        confidence=1.0,  # Backend-level confidence not always available
        is_formula=response.is_formula,
        formula_latex=response.formula_latex,
    )


def extract_text(
    page_image: PageImage,
    layout_result: LayoutResult,
    backend: OCRBackend,
) -> tuple[OCRResult, ...]:
    """Run OCR on text-type regions using the configured backend.

    Args:
        page_image: The page image to process.
        layout_result: Layout detection results for this page.
        backend: OCR backend instance (Transformers, Ollama, vLLM, or API).

    Returns:
        Frozen tuple of OCRResult for each text region.
    """
    text_regions = _filter_text_regions(layout_result.regions)
    if not text_regions:
        return ()

    results: list[OCRResult] = []
    for region in text_regions:
        cropped = _crop_region(page_image.image, region.bbox)
        task = _TASK_PROMPTS.get(region.label, "Text Recognition:")

        try:
            response = backend.recognize(cropped, task)
        except Exception as exc:
            raise RuntimeError(
                f"OCR failed for page {page_image.page_number}, "
                f"region {region.region_id}: {exc}"
            ) from exc

        if response.text.strip():
            results.append(_response_to_result(response, region.region_id))

    return tuple(results)
