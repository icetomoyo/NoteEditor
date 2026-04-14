"""Background extraction stage - remove text regions for editable mode.

Generates a clean background image by detecting and filling text regions.
Background complexity is classified as simple (solid/near-solid color),
gradient, or complex, with appropriate fill strategies for each.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import cv2
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


def _fill_complex(
    image: np.ndarray,
    mask: np.ndarray,
    lama_session: Any,
) -> np.ndarray:
    """Fill masked regions using LaMA inpainting model.

    LaMA expects input image (1, 3, H, W) float32 [0,1] and
    mask (1, 1, H, W) float32 [0,1]. Both are resized to 512x512
    for inference, then the result is resized back to original size.

    Args:
        image: Page image (H, W, 3), dtype uint8.
        mask: Text mask (H, W), 255=fill, 0=keep.
        lama_session: ONNX InferenceSession for LaMA model.

    Returns:
        New image with masked regions inpainted.
    """
    orig_h, orig_w = image.shape[:2]

    # Resize to 512x512 for LaMA
    img_resized = cv2.resize(image, (512, 512)).astype(np.float32) / 255.0
    mask_resized = cv2.resize(mask, (512, 512)).astype(np.float32) / 255.0

    # Reshape to NCHW
    img_input = np.transpose(img_resized, (2, 0, 1))[np.newaxis, ...]  # (1, 3, 512, 512)
    mask_input = mask_resized[np.newaxis, np.newaxis, ...]  # (1, 1, 512, 512)

    input_name_img = lama_session.get_inputs()[0].name
    input_name_mask = lama_session.get_inputs()[1].name

    outputs = lama_session.run(
        None, {input_name_img: img_input, input_name_mask: mask_input},
    )

    # Output: (1, 3, 512, 512) float32 [0, 1]
    output = outputs[0][0]  # (3, 512, 512)
    output = np.transpose(output, (1, 2, 0))  # (512, 512, 3)
    output = np.clip(output * 255, 0, 255).astype(np.uint8)

    # Resize back to original dimensions
    result = cv2.resize(output, (orig_w, orig_h))

    # Only replace masked regions — keep original non-masked pixels
    final = image.copy()
    final[mask == 255] = result[mask == 255]
    return final


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
    lama_session: Any = None,
) -> np.ndarray:
    """Extract a clean background image with text regions removed.

    Classifies the background complexity and applies the appropriate
    fill strategy:
    - Simple (solid/near-solid): median color fill
    - Gradient: per-row linear interpolation
    - Complex: LaMA inpainting if model available, else white fill

    Args:
        page_image: Source page image with rendered content.
        layout_result: Layout detection results with region positions.
        lama_session: Optional ONNX InferenceSession for LaMA model.

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

    # Complex background: try LaMA, fall back to white
    if lama_session is not None:
        try:
            return _fill_complex(image, mask, lama_session)
        except Exception as exc:
            logger.warning("LaMA inpainting failed, falling back to white fill: %s", exc)

    return _fill_fallback(image, mask)
