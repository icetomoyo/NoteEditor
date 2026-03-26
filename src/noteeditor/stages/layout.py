"""Layout detection stage - PP-DocLayout-V3 semantic region detection."""

from __future__ import annotations

import cv2
import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]

from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage

_MODEL_INPUT_SIZE = 800
_MODEL_OUTPUT_COLS = 8
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# PP-DocLayout-V3 label index → RegionLabel mapping (26 categories → 11 labels).
_LABEL_MAP: dict[int, RegionLabel] = {
    0: RegionLabel.HEADER,
    1: RegionLabel.FOOTER,
    2: RegionLabel.BODY_TEXT,
    3: RegionLabel.BODY_TEXT,  # aside_text
    4: RegionLabel.TITLE,
    5: RegionLabel.BODY_TEXT,  # paragraph_title
    6: RegionLabel.TITLE,  # doc_title
    7: RegionLabel.EQUATION,  # display_formula
    8: RegionLabel.EQUATION,  # inline_formula
    9: RegionLabel.EQUATION,  # formula_number
    10: RegionLabel.IMAGE,
    11: RegionLabel.TABLE,
    12: RegionLabel.BODY_TEXT,  # content
    13: RegionLabel.REFERENCE,
    14: RegionLabel.REFERENCE,  # reference_content
    15: RegionLabel.IMAGE,  # footer_image
    16: RegionLabel.IMAGE,  # header_image
    17: RegionLabel.IMAGE,  # chart
    18: RegionLabel.IMAGE,  # embedded_image
    19: RegionLabel.FIGURE_CAPTION,
    20: RegionLabel.UNKNOWN,  # abstract
    21: RegionLabel.BODY_TEXT,  # author
    22: RegionLabel.BODY_TEXT,  # text
    23: RegionLabel.UNKNOWN,  # keywords
    24: RegionLabel.UNKNOWN,  # date
    25: RegionLabel.UNKNOWN,  # section
}


def _preprocess(image: np.ndarray) -> np.ndarray:
    """Preprocess an image for PP-DocLayout-V3 inference.

    Resizes to 800x800 with direct stretch (no letterbox padding).
    This matches the model's training preprocessing: PP-DocLayout-V3 was
    trained with PaddleDetection's DetResize (keep_ratio=False), so letterbox
    padding would introduce padding artifacts the model never saw.

    Args:
        image: Input image in RGB format, shape (H, W, 3), dtype uint8.

    Returns:
        Preprocessed tensor, shape (1, 3, 800, 800), dtype float32.
    """
    resized = cv2.resize(image, (_MODEL_INPUT_SIZE, _MODEL_INPUT_SIZE))
    normalized = resized.astype(np.float32) / 255.0
    normalized = (normalized - _IMAGENET_MEAN) / _IMAGENET_STD
    # HWC → CHW, then add batch dimension
    transposed = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(transposed, axis=0)


def _parse_detections(
    raw: np.ndarray,
    page_image: PageImage,
) -> list[LayoutRegion]:
    """Parse raw model output into LayoutRegion objects.

    All detections are returned; confidence filtering is handled separately
    by ``_filter_low_confidence``.

    Args:
        raw: Raw model output, shape (N, 8), columns:
            [label_index, score, xmin, ymin, xmax, ymax, ...].
        page_image: Original page image for coordinate scaling.

    Returns:
        List of LayoutRegion objects (unfiltered).

    Raises:
        ValueError: If raw output shape is not (N, >=6).
    """
    if raw.size == 0:
        return []

    if raw.ndim != 2 or raw.shape[1] < 6:
        raise ValueError(
            f"Expected model output shape (N, {_MODEL_OUTPUT_COLS}), "
            f"got {raw.shape}"
        )

    scale_x = page_image.width_px / _MODEL_INPUT_SIZE
    scale_y = page_image.height_px / _MODEL_INPUT_SIZE
    regions: list[LayoutRegion] = []

    for idx, row in enumerate(raw):
        label_idx = int(row[0])
        confidence = float(row[1])

        label = _LABEL_MAP.get(label_idx, RegionLabel.UNKNOWN)
        xmin = float(row[2]) * scale_x
        ymin = float(row[3]) * scale_y
        xmax = float(row[4]) * scale_x
        ymax = float(row[5]) * scale_y

        width = max(0.0, xmax - xmin)
        height = max(0.0, ymax - ymin)

        bbox = BoundingBox(x=xmin, y=ymin, width=width, height=height)
        region_id = f"page{page_image.page_number}_region{idx}"
        regions.append(
            LayoutRegion(
                bbox=bbox, label=label, confidence=confidence, region_id=region_id,
            ),
        )

    return regions


def _filter_low_confidence(
    regions: list[LayoutRegion],
    threshold: float = 0.5,
) -> tuple[LayoutRegion, ...]:
    """Filter out low-confidence regions.

    Args:
        regions: List of layout regions.
        threshold: Minimum confidence score.

    Returns:
        Immutable tuple of regions above the threshold.
    """
    return tuple(r for r in regions if r.confidence >= threshold)


def detect_layout(
    page_image: PageImage,
    session: ort.InferenceSession,
    confidence_threshold: float = 0.5,
) -> LayoutResult:
    """Run layout detection on a single page.

    Args:
        page_image: The page image to analyze.
        session: ONNX Runtime InferenceSession for PP-DocLayout-V3.
        confidence_threshold: Minimum confidence for detected regions.

    Returns:
        Frozen LayoutResult with detected regions sorted by confidence descending.
    """
    input_tensor = _preprocess(page_image.image)
    input_name = session.get_inputs()[0].name
    try:
        outputs = session.run(None, {input_name: input_tensor})
    except Exception as exc:
        raise RuntimeError(
            f"Layout detection inference failed for page {page_image.page_number}: {exc}"
        ) from exc
    raw = outputs[0]

    regions = _parse_detections(raw, page_image)
    filtered = _filter_low_confidence(regions, confidence_threshold)
    sorted_regions = tuple(sorted(filtered, key=lambda r: r.confidence, reverse=True))

    return LayoutResult(page_number=page_image.page_number, regions=sorted_regions)
