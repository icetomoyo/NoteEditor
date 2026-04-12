"""Background extraction stage - remove text regions for editable mode.

Generates a clean background image by detecting and filling text regions.
Background complexity is classified as simple (solid/near-solid color),
gradient, or complex, with appropriate fill strategies for each.
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np

from noteeditor.models.layout import LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage

logger = logging.getLogger(__name__)

_TEXT_LABELS: frozenset[RegionLabel] = frozenset({
    RegionLabel.TITLE,
    RegionLabel.BODY_TEXT,
    RegionLabel.EQUATION,
    RegionLabel.CODE_BLOCK,
})

_SIMPLE_THRESHOLD = 15.0
_GRADIENT_THRESHOLD = 50.0


def _create_text_mask(
    image_shape: tuple[int, int],
    regions: tuple[LayoutRegion, ...],
) -> np.ndarray:
    """Create a binary mask of text regions.

    Args:
        image_shape: (height, width) of the image.
        regions: Layout regions to check.

    Returns:
        uint8 array (H, W) with 255 for text regions, 0 elsewhere.
    """
    h, w = image_shape
    mask = np.zeros((h, w), dtype=np.uint8)

    for region in regions:
        if region.label not in _TEXT_LABELS:
            continue
        bbox = region.bbox
        y1 = max(0, int(bbox.y))
        x1 = max(0, int(bbox.x))
        y2 = min(h, int(bbox.y + bbox.height))
        x2 = min(w, int(bbox.x + bbox.width))
        if y1 < y2 and x1 < x2:
            mask[y1:y2, x1:x2] = 255

    return mask


def _classify_background(
    image: np.ndarray,
    mask: np.ndarray,
) -> Literal["simple", "gradient", "complex"]:
    """Classify background complexity from non-masked pixels.

    Args:
        image: Page image (H, W, 3), dtype uint8.
        mask: Text mask (H, W), 255=text, 0=background.

    Returns:
        One of 'simple', 'gradient', 'complex'.
    """
    bg_pixels = image[mask == 0]
    if bg_pixels.size == 0:
        return "simple"

    std = float(np.std(bg_pixels.astype(np.float64)))
    if std < _SIMPLE_THRESHOLD:
        return "simple"
    if std < _GRADIENT_THRESHOLD:
        return "gradient"
    return "complex"


def _fill_simple(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fill masked regions with median color of background pixels.

    Args:
        image: Page image (H, W, 3), dtype uint8.
        mask: Text mask (H, W), 255=fill, 0=keep.

    Returns:
        New image with masked regions filled.
    """
    result = image.copy()
    bg_pixels = image[mask == 0]
    if bg_pixels.size == 0:
        result[mask == 255] = 255
        return result

    median_color = np.median(bg_pixels, axis=0).astype(np.uint8)
    result[mask == 255] = median_color
    return result


def _fill_gradient(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fill masked regions with per-row linear interpolation.

    For each row, finds leftmost and rightmost non-masked pixels
    and interpolates colors across masked regions. Uses vectorized
    numpy operations for performance (< 100ms at 300 DPI).

    Args:
        image: Page image (H, W, 3), dtype uint8.
        mask: Text mask (H, W), 255=fill, 0=keep.

    Returns:
        New image with masked regions interpolated.
    """
    result = image.copy()
    h, w = mask.shape

    # Find rows that have any masked pixels
    row_has_mask = mask.max(axis=1) > 0
    active_rows = np.where(row_has_mask)[0]

    if len(active_rows) == 0:
        return result

    for row in active_rows:
        mask_row = mask[row]
        text_cols = np.where(mask_row == 255)[0]

        left_col = int(text_cols[0])
        right_col = int(text_cols[-1])

        # Sample colors from just outside the masked region
        left_color = image[row, max(0, left_col - 1)].astype(np.float64)
        right_color = image[row, min(w - 1, right_col + 1)].astype(np.float64)

        # Vectorized interpolation across all 3 channels at once
        span = right_col - left_col + 1
        t = np.linspace(0.0, 1.0, span).reshape(-1, 1)  # (span, 1)
        interpolated = left_color + t * (right_color - left_color)  # (span, 3)
        result[row, left_col : right_col + 1] = np.clip(
            interpolated, 0, 255,
        ).astype(np.uint8)

    return result


def _fill_fallback(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Fill masked regions with white (fallback for complex backgrounds).

    Args:
        image: Page image (H, W, 3), dtype uint8.
        mask: Text mask (H, W), 255=fill, 0=keep.

    Returns:
        New image with masked regions filled white.
    """
    result = image.copy()
    result[mask == 255] = 255
    return result


def extract_background(
    page_image: PageImage,
    layout_result: LayoutResult,
) -> np.ndarray:
    """Extract a clean background image with text regions removed.

    Classifies the background complexity and applies the appropriate
    fill strategy:
    - Simple (solid/near-solid): median color fill
    - Gradient: per-row linear interpolation
    - Complex: white fill (LaMA inpainting deferred to v0.6.0)

    Args:
        page_image: Source page image with rendered content.
        layout_result: Layout detection results with region positions.

    Returns:
        Clean background image (H, W, 3), dtype uint8.
    """
    image = page_image.image
    mask = _create_text_mask(image.shape[:2], layout_result.regions)

    if mask.max() == 0:
        # No text regions → return unmodified
        return image.copy()

    complexity = _classify_background(image, mask)
    logger.debug(
        "Page %d background classified as '%s'",
        page_image.page_number,
        complexity,
    )

    if complexity == "simple":
        return _fill_simple(image, mask)
    if complexity == "gradient":
        return _fill_gradient(image, mask)
    return _fill_fallback(image, mask)
