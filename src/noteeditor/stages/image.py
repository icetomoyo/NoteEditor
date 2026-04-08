"""Image extraction stage - extract images from PDF pages.

Prioritizes embedded PDF resources (higher resolution) and falls back
to cropping from the rendered page image when no embedded resource
matches a layout-detected IMAGE region.
"""

from __future__ import annotations

import logging

import numpy as np

from noteeditor.models.content import ExtractedImage
from noteeditor.models.layout import LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import BoundingBox, EmbeddedResource, PageImage

logger = logging.getLogger(__name__)


def _filter_image_regions(
    regions: tuple[LayoutRegion, ...],
) -> tuple[LayoutRegion, ...]:
    """Filter layout regions to IMAGE label only."""
    return tuple(r for r in regions if r.label == RegionLabel.IMAGE)


def _compute_iou(a: BoundingBox, b: BoundingBox) -> float:
    """Compute Intersection over Union of two bounding boxes.

    Returns a value between 0.0 (no overlap) and 1.0 (perfect overlap).
    """
    x1 = max(a.x, b.x)
    y1 = max(a.y, b.y)
    x2 = min(a.x + a.width, b.x + b.width)
    y2 = min(a.y + a.height, b.y + b.height)

    if x2 <= x1 or y2 <= y1:
        return 0.0

    intersection = (x2 - x1) * (y2 - y1)
    area_a = a.width * a.height
    area_b = b.width * b.height
    union = area_a + area_b - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def _match_embedded(
    region: LayoutRegion,
    resources: tuple[EmbeddedResource, ...],
    iou_threshold: float = 0.5,
) -> EmbeddedResource | None:
    """Find the best matching embedded resource for a layout region.

    Args:
        region: Layout region to match.
        resources: Available embedded resources.
        iou_threshold: Minimum IoU for a valid match.

    Returns:
        Best matching EmbeddedResource, or None if no match exceeds threshold.
    """
    best: EmbeddedResource | None = None
    best_iou = iou_threshold

    for resource in resources:
        iou = _compute_iou(region.bbox, resource.bbox)
        if iou > best_iou:
            best_iou = iou
            best = resource

    return best


def _crop_image(
    image: np.ndarray,
    bbox: BoundingBox,
) -> np.ndarray:
    """Crop an image region with bbox clamping to image bounds.

    Args:
        image: Source image (H, W, 3).
        bbox: Bounding box in pixel coordinates.

    Returns:
        Cropped image copy.
    """
    h, w = image.shape[:2]
    y1 = max(0, int(bbox.y))
    x1 = max(0, int(bbox.x))
    y2 = min(h, int(bbox.y + bbox.height))
    x2 = min(w, int(bbox.x + bbox.width))

    if y1 >= y2 or x1 >= x2:
        return image.copy()

    return image[y1:y2, x1:x2].copy()


def extract_images(
    page_image: PageImage,
    layout_result: LayoutResult,
) -> tuple[ExtractedImage, ...]:
    """Extract images from IMAGE-labeled regions.

    For each IMAGE region in the layout, tries to match an embedded PDF
    resource (higher quality). Falls back to cropping from the rendered
    page image when no embedded resource matches.

    Args:
        page_image: Source page with rendered image and optional embedded resources.
        layout_result: Layout detection results with region positions.

    Returns:
        Tuple of ExtractedImage objects, one per IMAGE region.
    """
    image_regions = _filter_image_regions(layout_result.regions)

    if not image_regions:
        return ()

    results: list[ExtractedImage] = []

    for region in image_regions:
        matched = _match_embedded(region, page_image.embedded_images)

        if matched is not None:
            results.append(
                ExtractedImage(
                    region_id=region.region_id,
                    image=matched.image,
                    source="embedded",
                    bbox=region.bbox,
                    width_px=matched.width_px,
                    height_px=matched.height_px,
                ),
            )
            logger.debug(
                "Region %s: matched embedded resource %d",
                region.region_id,
                matched.index,
            )
        else:
            cropped = _crop_image(page_image.image, region.bbox)
            h_px, w_px = cropped.shape[:2]
            results.append(
                ExtractedImage(
                    region_id=region.region_id,
                    image=cropped,
                    source="cropped",
                    bbox=region.bbox,
                    width_px=w_px,
                    height_px=h_px,
                ),
            )
            logger.debug(
                "Region %s: cropped from page image", region.region_id,
            )

    return tuple(results)
