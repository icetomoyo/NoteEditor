"""Text style estimation stage - font size and color from page image."""

from __future__ import annotations

import logging

import numpy as np

from noteeditor.models.content import OCRResult, TextStyle
from noteeditor.models.layout import BoundingBox, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage

logger = logging.getLogger(__name__)

# Text region labels eligible for style estimation.
_TEXT_LABELS: frozenset[RegionLabel] = frozenset(
    {
        RegionLabel.TITLE,
        RegionLabel.BODY_TEXT,
        RegionLabel.EQUATION,
        RegionLabel.CODE_BLOCK,
    }
)


def _estimate_font_size(
    bbox_height_px: float,
    dpi: int,
    line_count: int = 1,
) -> int:
    """Estimate font size in points from bbox height in pixels.

    For multi-line regions, divides bbox height by line count first to get
    the per-line height, then applies the standard formula.

    Formula: font_size_pt = (bbox_height_px / line_count) * (72 / dpi) * 0.8
    The 0.8 factor accounts for typical line-height vs font-size ratio.
    """
    lines = max(1, line_count)
    per_line_height = bbox_height_px / lines
    return max(1, int(per_line_height * (72 / dpi) * 0.8))


def _sample_font_color(
    image: np.ndarray,
    bbox: BoundingBox,
) -> tuple[int, int, int]:
    """Sample dominant text color from page image at bbox region.

    Samples the top-center portion of the bbox, finds the most common
    non-white/non-background color. Falls back to black if no dark
    pixels are found.
    """
    img_h, img_w = image.shape[:2]

    # Sample region: top 1/3, middle 80% width of bbox
    top_y = max(0, int(bbox.y))
    bot_y = min(img_h, int(bbox.y + bbox.height * 0.33))
    left_x = max(0, int(bbox.x + bbox.width * 0.1))
    right_x = min(img_w, int(bbox.x + bbox.width * 0.9))

    if top_y >= bot_y or left_x >= right_x:
        return (0, 0, 0)

    region = image[top_y:bot_y, left_x:right_x]
    if region.size == 0:
        return (0, 0, 0)

    # Reshape to list of pixels
    pixels = region.reshape(-1, 3)

    # Filter out near-white pixels (background)
    # Consider pixels with all channels > 230 as background
    brightness = pixels.astype(np.int16).sum(axis=1)
    dark_mask = brightness < 690  # 230 * 3
    dark_pixels = pixels[dark_mask]

    if len(dark_pixels) == 0:
        return (0, 0, 0)

    # Find the most common color among dark pixels using binning
    # Quantize to reduce color space, then find most frequent
    quantized = ((dark_pixels.astype(np.int32) // 16) * 16).astype(np.uint8)
    # Encode as single key using base-256 for safe decomposition
    color_keys = (
        quantized[:, 0].astype(np.int32) * 65536
        + quantized[:, 1].astype(np.int32) * 256
        + quantized[:, 2].astype(np.int32)
    )
    unique_keys, counts = np.unique(color_keys, return_counts=True)
    most_common_idx = counts.argmax()
    most_common_key = int(unique_keys[most_common_idx])

    r = most_common_key // 65536
    g = (most_common_key % 65536) // 256
    b = most_common_key % 256

    return (r, g, b)


def _count_lines(text: str) -> int:
    """Count lines in OCR text. Returns at least 1."""
    return max(1, text.count("\n") + 1)


def estimate_styles(
    page_image: PageImage,
    layout_result: LayoutResult,
    ocr_results: tuple[OCRResult, ...] = (),
) -> tuple[TextStyle, ...]:
    """Estimate font size and color for text regions.

    For each text-labeled region (TITLE, BODY_TEXT, EQUATION, CODE_BLOCK),
    estimates the font size from the bbox height (divided by line count
    when OCR results are available) and samples the dominant text color
    from the page image.
    """
    ocr_by_region: dict[str, OCRResult] = {o.region_id: o for o in ocr_results}
    results: list[TextStyle] = []

    for region in layout_result.regions:
        if region.label not in _TEXT_LABELS:
            continue

        ocr = ocr_by_region.get(region.region_id)
        line_count = _count_lines(ocr.text) if ocr is not None else 1

        font_size = _estimate_font_size(
            region.bbox.height, page_image.dpi, line_count=line_count,
        )
        font_color = _sample_font_color(page_image.image, region.bbox)

        results.append(
            TextStyle(
                region_id=region.region_id,
                font_size_pt=font_size,
                font_color_rgb=font_color,
            )
        )

    return tuple(results)
