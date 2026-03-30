"""OCR stage - GLM-OCR text recognition."""

from __future__ import annotations

import base64
import json
import logging
from io import BytesIO

import httpx
import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]

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

_ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


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


def _encode_image_base64(image: np.ndarray) -> str:
    """Encode a numpy RGB image as JPEG base64 string.

    Args:
        image: Image array (H, W, 3), dtype uint8, RGB.

    Returns:
        Base64-encoded JPEG string.
    """
    try:
        from PIL import Image as PILImage

        buf = BytesIO()
        PILImage.fromarray(image).save(buf, format="JPEG", quality=95)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        # Fallback: encode raw bytes as base64 (less efficient but functional)
        return base64.b64encode(image.tobytes()).decode("ascii")


def _parse_api_response(data: dict[str, object], region_id: str) -> OCRResult:
    """Parse a single region's data from Zhipu API response into OCRResult.

    Args:
        data: Dict with keys 'text', 'confidence', 'is_formula'.
            Optional: 'formula_latex'.
        region_id: Region identifier for the OCRResult.

    Returns:
        Frozen OCRResult.

    Raises:
        ValueError: If required keys are missing from data.
    """
    for key in ("text", "confidence", "is_formula"):
        if key not in data:
            raise ValueError(f"Missing required key '{key}' in API response for {region_id}")

    conf_raw = data["confidence"]
    confidence = float(conf_raw) if isinstance(conf_raw, (int, float, str)) else 0.0
    formula_val = data.get("formula_latex")
    return OCRResult(
        region_id=region_id,
        text=str(data["text"]),
        confidence=confidence,
        is_formula=bool(data["is_formula"]),
        formula_latex=str(formula_val) if formula_val is not None else None,
    )


def _run_ocr_onnx(
    cropped: np.ndarray,
    session: ort.InferenceSession,
) -> OCRResult | None:
    """Run GLM-OCR ONNX inference on a single cropped region.

    Args:
        cropped: Cropped region image (H, W, 3), dtype uint8.
        session: ONNX Runtime InferenceSession.

    Returns:
        OCRResult or None if inference produced empty output.
    """
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: cropped[np.newaxis, ...]})

    text_arr = outputs[0]
    conf_arr = outputs[1]
    formula_arr = outputs[2] if len(outputs) > 2 else np.array([[0.0]])

    text = str(text_arr[0, 0]) if text_arr.size > 0 else ""
    if not text.strip():
        return None

    confidence = float(conf_arr[0, 0]) if conf_arr.size > 0 else 0.0
    is_formula = bool(formula_arr[0, 0]) if formula_arr.size > 0 else False

    return OCRResult(
        region_id="",  # Caller fills this in
        text=text,
        confidence=confidence,
        is_formula=is_formula,
        formula_latex=text if is_formula else None,
    )


def _run_ocr_api(
    cropped: np.ndarray,
    api_key: str,
    api_url: str,
    region_id: str,
) -> OCRResult:
    """Run GLM-OCR API inference on a single cropped region.

    Args:
        cropped: Cropped region image (H, W, 3), dtype uint8.
        api_key: Zhipu API key.
        api_url: API endpoint URL.
        region_id: Region identifier for error context.

    Returns:
        OCRResult.

    Raises:
        RuntimeError: If the API request fails.
    """
    img_b64 = _encode_image_base64(cropped)

    payload = {
        "model": "glm-4v-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Extract all text from this image. "
                            "Return JSON with keys: text, confidence (0-1), "
                            "is_formula (bool). If formula, include formula_latex."
                        ),
                    },
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(api_url, json=payload, headers=headers)
    except Exception as exc:
        raise RuntimeError(
            f"OCR API request failed for {region_id}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"OCR API request failed for {region_id}: "
            f"HTTP {response.status_code} - {response.text}"
        )

    body = response.json()
    content_str = body["choices"][0]["message"]["content"]

    # Try parsing the content as JSON
    try:
        data = json.loads(content_str)
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat entire content as plain text
        data = {
            "text": content_str,
            "confidence": 0.5,
            "is_formula": False,
        }

    return _parse_api_response(data, region_id)


def extract_text(
    page_image: PageImage,
    layout_result: LayoutResult,
    session: ort.InferenceSession,
) -> tuple[OCRResult, ...]:
    """Run OCR on text-type regions using GLM-OCR (ONNX mode).

    Args:
        page_image: The page image to process.
        layout_result: Layout detection results for this page.
        session: ONNX Runtime InferenceSession for GLM-OCR.

    Returns:
        Frozen tuple of OCRResult for each text region.
    """
    text_regions = _filter_text_regions(layout_result.regions)
    if not text_regions:
        return ()

    results: list[OCRResult] = []
    for region in text_regions:
        cropped = _crop_region(page_image.image, region.bbox)
        try:
            ocr_result = _run_ocr_onnx(cropped, session)
        except Exception as exc:
            raise RuntimeError(
                f"OCR inference failed for page {page_image.page_number}, "
                f"region {region.region_id}: {exc}"
            ) from exc

        if ocr_result is not None:
            results.append(OCRResult(
                region_id=region.region_id,
                text=ocr_result.text,
                confidence=ocr_result.confidence,
                is_formula=ocr_result.is_formula,
                formula_latex=ocr_result.formula_latex,
            ))

    return tuple(results)


def extract_text_api(
    page_image: PageImage,
    layout_result: LayoutResult,
    api_key: str,
    api_url: str = _ZHIPU_API_URL,
) -> tuple[OCRResult, ...]:
    """Run OCR on text-type regions using Zhipu GLM-OCR API.

    Args:
        page_image: The page image to process.
        layout_result: Layout detection results for this page.
        api_key: Zhipu BigModel API key.
        api_url: API endpoint URL.

    Returns:
        Frozen tuple of OCRResult for each text region.
    """
    text_regions = _filter_text_regions(layout_result.regions)
    if not text_regions:
        return ()

    results: list[OCRResult] = []
    for region in text_regions:
        cropped = _crop_region(page_image.image, region.bbox)
        ocr_result = _run_ocr_api(cropped, api_key, api_url, region.region_id)
        results.append(ocr_result)

    return tuple(results)
