"""Tests for stages/ocr.py - OCR text extraction."""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage
from noteeditor.stages.ocr import (
    _crop_region,
    _encode_image_base64,
    _filter_text_regions,
    _parse_api_response,
    extract_text,
    extract_text_api,
)


def _make_page_image(
    page_number: int = 0,
    width_px: int = 800,
    height_px: int = 600,
    dpi: int = 300,
) -> PageImage:
    """Create a PageImage with synthetic image data."""
    image = np.random.randint(0, 255, (height_px, width_px, 3), dtype=np.uint8)
    aspect_ratio = width_px / height_px if height_px > 0 else 1.0
    return PageImage(
        page_number=page_number,
        width_px=width_px,
        height_px=height_px,
        dpi=dpi,
        aspect_ratio=aspect_ratio,
        image=image,
    )


def _make_layout_result(
    page_number: int = 0,
    regions: list[LayoutRegion] | None = None,
) -> LayoutResult:
    """Create a LayoutResult with optional regions."""
    return LayoutResult(page_number=page_number, regions=tuple(regions or []))


def _make_text_region(
    region_id: str = "page0_region0",
    x: float = 50.0,
    y: float = 50.0,
    width: float = 200.0,
    height: float = 30.0,
    label: RegionLabel = RegionLabel.BODY_TEXT,
    confidence: float = 0.9,
) -> LayoutRegion:
    """Create a LayoutRegion with sensible defaults."""
    return LayoutRegion(
        bbox=BoundingBox(x=x, y=y, width=width, height=height),
        label=label,
        confidence=confidence,
        region_id=region_id,
    )


def _make_mock_ocr_session(
    outputs: list[dict] | None = None,
) -> MagicMock:
    """Create a mock ONNX InferenceSession for GLM-OCR.

    Each dict in outputs should have keys:
        text: str
        confidence: float
        is_formula: bool
        formula_latex: str | None

    Each region call returns the next output in sequence.
    """
    session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "image"
    session.get_inputs.return_value = [mock_input]
    session.get_providers.return_value = ["CPUExecutionProvider"]

    if outputs:
        # Build a sequence of return values, one per region call.
        side_effects = []
        for o in outputs:
            side_effects.append([
                np.array([[o["text"]]]),
                np.array([[o["confidence"]]], dtype=np.float32),
                np.array([[o["is_formula"]]], dtype=np.float32),
            ])
        session.run.side_effect = side_effects
    else:
        session.run.return_value = [
            np.array([[""]]), np.array([[0.0]], dtype=np.float32),
            np.array([[0.0]], dtype=np.float32),
        ]
    return session


class TestFilterTextRegions:
    """Tests for _filter_text_regions()."""

    def test_keeps_body_text(self) -> None:
        """BODY_TEXT regions are kept."""
        region = _make_text_region(label=RegionLabel.BODY_TEXT)
        result = _filter_text_regions((region,))
        assert len(result) == 1
        assert result[0].label == RegionLabel.BODY_TEXT

    def test_keeps_title(self) -> None:
        """TITLE regions are kept."""
        region = _make_text_region(label=RegionLabel.TITLE)
        result = _filter_text_regions((region,))
        assert len(result) == 1

    def test_keeps_equation(self) -> None:
        """EQUATION regions are kept."""
        region = _make_text_region(label=RegionLabel.EQUATION)
        result = _filter_text_regions((region,))
        assert len(result) == 1

    def test_keeps_code_block(self) -> None:
        """CODE_BLOCK regions are kept."""
        region = _make_text_region(label=RegionLabel.CODE_BLOCK)
        result = _filter_text_regions((region,))
        assert len(result) == 1

    def test_filters_image(self) -> None:
        """IMAGE regions are excluded."""
        region = _make_text_region(label=RegionLabel.IMAGE)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_table(self) -> None:
        """TABLE regions are excluded."""
        region = _make_text_region(label=RegionLabel.TABLE)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_header_footer(self) -> None:
        """HEADER and FOOTER regions are excluded."""
        regions = (
            _make_text_region(label=RegionLabel.HEADER),
            _make_text_region(label=RegionLabel.FOOTER),
        )
        result = _filter_text_regions(regions)
        assert len(result) == 0

    def test_filters_figure_caption(self) -> None:
        """FIGURE_CAPTION regions are excluded."""
        region = _make_text_region(label=RegionLabel.FIGURE_CAPTION)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_reference(self) -> None:
        """REFERENCE regions are excluded."""
        region = _make_text_region(label=RegionLabel.REFERENCE)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_unknown(self) -> None:
        """UNKNOWN regions are excluded."""
        region = _make_text_region(label=RegionLabel.UNKNOWN)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_mixed_regions(self) -> None:
        """Only text-type regions are kept from a mixed set."""
        regions = (
            _make_text_region(region_id="r1", label=RegionLabel.TITLE),
            _make_text_region(region_id="r2", label=RegionLabel.IMAGE),
            _make_text_region(region_id="r3", label=RegionLabel.BODY_TEXT),
            _make_text_region(region_id="r4", label=RegionLabel.TABLE),
            _make_text_region(region_id="r5", label=RegionLabel.EQUATION),
        )
        result = _filter_text_regions(regions)
        assert len(result) == 3
        assert {r.region_id for r in result} == {"r1", "r3", "r5"}

    def test_empty_input(self) -> None:
        """Empty input returns empty tuple."""
        result = _filter_text_regions(())
        assert result == ()
        assert isinstance(result, tuple)

    def test_returns_tuple(self) -> None:
        """Result is always a tuple."""
        region = _make_text_region()
        result = _filter_text_regions((region,))
        assert isinstance(result, tuple)


class TestCropRegion:
    """Tests for _crop_region()."""

    def test_basic_crop(self) -> None:
        """Crops correct region from image."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        image[100:130, 200:400] = 255  # white rectangle
        bbox = BoundingBox(x=200.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.shape == (30, 200, 3)
        assert np.all(cropped == 255)

    def test_padding_applied(self) -> None:
        """Default padding of 10px is applied."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape == (50, 220, 3)

    def test_custom_padding(self) -> None:
        """Custom padding value is applied."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=20)
        assert cropped.shape == (70, 240, 3)

    def test_clamp_at_top_boundary(self) -> None:
        """Padding is clamped when region is at top edge."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=0.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        # y starts at 0, padding can only extend down, not above
        assert cropped.shape[0] == 40  # 30 + 10 (only bottom padding)
        assert cropped.shape[1] == 220  # 200 + 10*2

    def test_clamp_at_left_boundary(self) -> None:
        """Padding is clamped when region is at left edge."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=0.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[1] == 210  # 200 + 10 right padding (left clamped)

    def test_clamp_at_right_boundary(self) -> None:
        """Padding is clamped when region is at right edge."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=750.0, y=100.0, width=50.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[1] == 60  # 50 + 10 (only left padding, right is at boundary)

    def test_clamp_at_bottom_boundary(self) -> None:
        """Padding is clamped when region is at bottom edge."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=570.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[0] == 40  # 30 + 10 (only top padding)

    def test_clamp_all_boundaries(self) -> None:
        """Region larger than image is clamped to image bounds."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = BoundingBox(x=-50.0, y=-50.0, width=200.0, height=200.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.shape == (100, 100, 3)

    def test_output_is_copy(self) -> None:
        """Cropped region is a view, not a copy of original array (numpy slicing)."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=100.0, y=100.0, width=50.0, height=50.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.shape == (50, 50, 3)
        assert cropped.base is image  # numpy slice shares memory

    def test_output_dtype(self) -> None:
        """Output preserves input dtype."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=100.0, y=100.0, width=50.0, height=50.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.dtype == np.uint8


class TestEncodeImageBase64:
    """Tests for _encode_image_base64()."""

    def test_returns_string(self) -> None:
        """Returns a base64-encoded string."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _encode_image_base64(image)
        assert isinstance(result, str)

    def test_decodeable(self) -> None:
        """Output can be decoded back to valid bytes."""
        image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = _encode_image_base64(image)
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_deterministic(self) -> None:
        """Same input produces same output."""
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        r1 = _encode_image_base64(image)
        r2 = _encode_image_base64(image)
        assert r1 == r2

    def test_different_images_different_output(self) -> None:
        """Different images produce different base64 strings."""
        image1 = np.zeros((50, 50, 3), dtype=np.uint8)
        image2 = np.full((50, 50, 3), 255, dtype=np.uint8)
        assert _encode_image_base64(image1) != _encode_image_base64(image2)


class TestParseApiResponse:
    """Tests for _parse_api_response()."""

    def test_text_result(self) -> None:
        """Parses a simple text response."""
        data = {
            "text": "Hello World",
            "confidence": 0.95,
            "is_formula": False,
        }
        result = _parse_api_response(data, "page0_region0")
        assert result.text == "Hello World"
        assert result.confidence == pytest.approx(0.95)
        assert result.is_formula is False
        assert result.formula_latex is None
        assert result.region_id == "page0_region0"

    def test_formula_result(self) -> None:
        """Parses a formula response with LaTeX."""
        data = {
            "text": "E = mc^2",
            "confidence": 0.88,
            "is_formula": True,
            "formula_latex": "E = mc^2",
        }
        result = _parse_api_response(data, "page0_region1")
        assert result.text == "E = mc^2"
        assert result.is_formula is True
        assert result.formula_latex == "E = mc^2"

    def test_formula_without_latex(self) -> None:
        """Formula with no LaTeX field sets formula_latex to None."""
        data = {
            "text": "x^2",
            "confidence": 0.7,
            "is_formula": True,
        }
        result = _parse_api_response(data, "page0_region2")
        assert result.is_formula is True
        assert result.formula_latex is None

    def test_region_id_preserved(self) -> None:
        """Region ID from input is preserved in OCRResult."""
        data = {"text": "test", "confidence": 0.9, "is_formula": False}
        result = _parse_api_response(data, "page5_region3")
        assert result.region_id == "page5_region3"

    def test_missing_text_raises(self) -> None:
        """Missing 'text' key raises ValueError."""
        data = {"confidence": 0.9, "is_formula": False}
        with pytest.raises(ValueError, match="text"):
            _parse_api_response(data, "r1")

    def test_missing_confidence_raises(self) -> None:
        """Missing 'confidence' key raises ValueError."""
        data = {"text": "hello", "is_formula": False}
        with pytest.raises(ValueError, match="confidence"):
            _parse_api_response(data, "r1")

    def test_missing_is_formula_raises(self) -> None:
        """Missing 'is_formula' key raises ValueError."""
        data = {"text": "hello", "confidence": 0.9}
        with pytest.raises(ValueError, match="is_formula"):
            _parse_api_response(data, "r1")

    def test_result_is_frozen(self) -> None:
        """OCRResult is immutable."""
        data = {"text": "frozen", "confidence": 0.9, "is_formula": False}
        result = _parse_api_response(data, "r1")
        with pytest.raises(AttributeError):
            result.text = "mutated"  # type: ignore[misc]


class TestExtractText:
    """Tests for extract_text() - ONNX mode."""

    def test_no_text_regions(self) -> None:
        """Empty layout result returns empty tuple."""
        page = _make_page_image()
        layout = _make_layout_result(regions=[])
        session = _make_mock_ocr_session()
        result = extract_text(page, layout, session)
        assert result == ()

    def test_non_text_regions_skipped(self) -> None:
        """Non-text regions (IMAGE, TABLE) are skipped."""
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.IMAGE),
            _make_text_region(region_id="r2", label=RegionLabel.TABLE),
        ]
        layout = _make_layout_result(regions=regions)
        session = _make_mock_ocr_session()
        result = extract_text(page, layout, session)
        assert result == ()
        session.run.assert_not_called()

    def test_single_text_region(self) -> None:
        """Single text region produces one OCRResult."""
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="page0_region0", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        session = _make_mock_ocr_session([
            {"text": "Hello World", "confidence": 0.95, "is_formula": False},
        ])
        result = extract_text(page, layout, session)
        assert len(result) == 1
        assert result[0].text == "Hello World"
        assert result[0].confidence == pytest.approx(0.95)
        assert result[0].is_formula is False
        assert result[0].region_id == "page0_region0"

    def test_multiple_text_regions(self) -> None:
        """Multiple text regions produce corresponding OCRResults."""
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.TITLE),
            _make_text_region(region_id="r2", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        session = _make_mock_ocr_session([
            {"text": "Title", "confidence": 0.9, "is_formula": False},
            {"text": "Body text", "confidence": 0.85, "is_formula": False},
        ])
        result = extract_text(page, layout, session)
        assert len(result) == 2
        assert result[0].text == "Title"
        assert result[1].text == "Body text"

    def test_formula_region(self) -> None:
        """Formula regions produce OCRResult with is_formula=True."""
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="eq1", label=RegionLabel.EQUATION),
        ]
        layout = _make_layout_result(regions=regions)
        session = _make_mock_ocr_session([
            {"text": "a^2+b^2=c^2", "confidence": 0.92, "is_formula": True,
             "formula_latex": "a^2+b^2=c^2"},
        ])
        result = extract_text(page, layout, session)
        assert len(result) == 1
        assert result[0].is_formula is True
        assert result[0].formula_latex == "a^2+b^2=c^2"

    def test_mixed_regions_only_text_processed(self) -> None:
        """Only text-type regions are processed from mixed layout."""
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.TITLE),
            _make_text_region(region_id="r2", label=RegionLabel.IMAGE),
            _make_text_region(region_id="r3", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        session = _make_mock_ocr_session([
            {"text": "Title", "confidence": 0.9, "is_formula": False},
            {"text": "Body", "confidence": 0.8, "is_formula": False},
        ])
        result = extract_text(page, layout, session)
        assert len(result) == 2

    def test_returns_tuple(self) -> None:
        """Result is always a tuple."""
        page = _make_page_image()
        layout = _make_layout_result()
        session = _make_mock_ocr_session()
        result = extract_text(page, layout, session)
        assert isinstance(result, tuple)

    def test_inference_error_wrapped(self) -> None:
        """ONNX inference errors are wrapped in RuntimeError with page context."""
        page = _make_page_image(page_number=3)
        regions = [_make_text_region(label=RegionLabel.BODY_TEXT)]
        layout = _make_layout_result(regions=regions)
        session = MagicMock()
        mock_input = MagicMock()
        mock_input.name = "image"
        session.get_inputs.return_value = [mock_input]
        session.run.side_effect = RuntimeError("ONNX: out of memory")
        with pytest.raises(RuntimeError, match="OCR inference failed for page 3"):
            extract_text(page, layout, session)


class TestExtractTextApi:
    """Tests for extract_text_api() - Zhipu API mode."""

    def _make_api_response(self, text: str, confidence: float, is_formula: bool = False,
                           formula_latex: str | None = None) -> dict:
        """Build a mock Zhipu API response."""
        content: dict = {
            "text": text,
            "confidence": confidence,
            "is_formula": is_formula,
        }
        if formula_latex is not None:
            content["formula_latex"] = formula_latex
        return {
            "choices": [
                {"message": {"content": json.dumps(content)}},
            ],
        }

    @patch("noteeditor.stages.ocr.httpx")
    def test_no_text_regions(self, mock_httpx: MagicMock) -> None:
        """Empty layout result returns empty tuple without API calls."""
        page = _make_page_image()
        layout = _make_layout_result(regions=[])
        result = extract_text_api(page, layout, "fake-key")
        assert result == ()
        mock_httpx.Client.assert_not_called()

    @patch("noteeditor.stages.ocr.httpx")
    def test_single_region(self, mock_httpx: MagicMock) -> None:
        """Single text region produces one OCRResult from API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._make_api_response(
            "API Text", 0.93,
        )
        mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_response

        page = _make_page_image()
        regions = [_make_text_region(region_id="r1", label=RegionLabel.BODY_TEXT)]
        layout = _make_layout_result(regions=regions)

        result = extract_text_api(page, layout, "fake-key")
        assert len(result) == 1
        assert result[0].text == "API Text"
        assert result[0].confidence == pytest.approx(0.93)
        assert result[0].region_id == "r1"

    @patch("noteeditor.stages.ocr.httpx")
    def test_api_error_raises_runtime_error(self, mock_httpx: MagicMock) -> None:
        """HTTP error response raises RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_response

        page = _make_page_image()
        regions = [_make_text_region(label=RegionLabel.BODY_TEXT)]
        layout = _make_layout_result(regions=regions)

        with pytest.raises(RuntimeError, match="OCR API request failed"):
            extract_text_api(page, layout, "fake-key")

    @patch("noteeditor.stages.ocr.httpx")
    def test_network_error_raises_runtime_error(self, mock_httpx: MagicMock) -> None:
        """Network errors are wrapped in RuntimeError."""
        mock_httpx.Client.return_value.__enter__.return_value.post.side_effect = (
            ConnectionError("Network unreachable")
        )

        page = _make_page_image()
        regions = [_make_text_region(label=RegionLabel.BODY_TEXT)]
        layout = _make_layout_result(regions=regions)

        with pytest.raises(RuntimeError, match="OCR API request failed"):
            extract_text_api(page, layout, "fake-key")

    @patch("noteeditor.stages.ocr.httpx")
    def test_returns_tuple(self, mock_httpx: MagicMock) -> None:
        """Result is always a tuple."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = self._make_api_response("Text", 0.9)
        mock_httpx.Client.return_value.__enter__.return_value.post.return_value = mock_response

        page = _make_page_image()
        regions = [_make_text_region(label=RegionLabel.BODY_TEXT)]
        layout = _make_layout_result(regions=regions)

        result = extract_text_api(page, layout, "fake-key")
        assert isinstance(result, tuple)

    @patch("noteeditor.stages.ocr.httpx")
    def test_non_text_regions_skipped(self, mock_httpx: MagicMock) -> None:
        """Non-text regions don't trigger API calls."""
        page = _make_page_image()
        regions = [_make_text_region(label=RegionLabel.IMAGE)]
        layout = _make_layout_result(regions=regions)

        result = extract_text_api(page, layout, "fake-key")
        assert result == ()
        mock_httpx.Client.return_value.__enter__.return_value.post.assert_not_called()
