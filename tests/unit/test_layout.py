"""Tests for stages/layout.py - Layout detection."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage
from noteeditor.stages.layout import (
    _filter_low_confidence,
    _parse_detections,
    _preprocess,
    detect_layout,
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


def _make_mock_session(output: np.ndarray | None = None) -> MagicMock:
    """Create a mock ONNX InferenceSession."""
    session = MagicMock()
    mock_input = MagicMock()
    mock_input.name = "image"
    session.get_inputs.return_value = [mock_input]
    session.get_providers.return_value = ["CPUExecutionProvider"]

    if output is not None:
        session.run.return_value = [output]
    else:
        session.run.return_value = [np.zeros((0, 8), dtype=np.float32)]
    return session


class TestPreprocess:
    """Tests for _preprocess()."""

    def test_output_shape(self) -> None:
        """Output shape is (1, 3, 800, 800)."""
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        result = _preprocess(image)
        assert result.shape == (1, 3, 800, 800)

    def test_output_dtype(self) -> None:
        """Output is float32."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _preprocess(image)
        assert result.dtype == np.float32

    def test_values_not_raw_pixels(self) -> None:
        """Normalized values differ from raw 0-255 pixel values."""
        image = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = _preprocess(image)
        assert np.all(result != 0)

    def test_normalization_exact_values(self) -> None:
        """Normalization produces exact ImageNet-normalized values."""
        image = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = _preprocess(image)

        # 128/255 = 0.50196...; ImageNet: (x - mean) / std
        expected_r = (128.0 / 255.0 - 0.485) / 0.229
        expected_g = (128.0 / 255.0 - 0.456) / 0.224
        expected_b = (128.0 / 255.0 - 0.406) / 0.225

        assert result[0, 0, 0, 0] == pytest.approx(expected_r)
        assert result[0, 1, 0, 0] == pytest.approx(expected_g)
        assert result[0, 2, 0, 0] == pytest.approx(expected_b)

    def test_different_input_sizes(self) -> None:
        """Any input size is resized to 800x800."""
        for h, w in [(600, 800), (1024, 768), (2550, 3300)]:
            image = np.zeros((h, w, 3), dtype=np.uint8)
            result = _preprocess(image)
            assert result.shape == (1, 3, 800, 800)


class TestParseDetections:
    """Tests for _parse_detections()."""

    def test_empty_detections(self) -> None:
        """Empty raw output returns empty list."""
        raw = np.zeros((0, 8), dtype=np.float32)
        page = _make_page_image()
        result = _parse_detections(raw, page)
        assert result == []

    def test_single_detection(self) -> None:
        """Single detection is parsed correctly."""
        raw = np.array(
            [[6, 0.95, 100.0, 50.0, 400.0, 100.0, 0.0, 0.0]],
            dtype=np.float32,
        )
        page = _make_page_image(width_px=800, height_px=600)
        result = _parse_detections(raw, page)
        assert len(result) == 1
        assert result[0].label == RegionLabel.TITLE
        assert result[0].confidence == pytest.approx(0.95)
        assert result[0].region_id == "page0_region0"

    def test_coordinate_scaling(self) -> None:
        """Coordinates are scaled from 800x800 to image dimensions."""
        raw = np.array(
            [[22, 0.9, 0.0, 0.0, 800.0, 800.0, 0.0, 0.0]],
            dtype=np.float32,
        )
        page = _make_page_image(width_px=1600, height_px=1200)
        result = _parse_detections(raw, page)
        assert result[0].bbox.x == pytest.approx(0.0)
        assert result[0].bbox.y == pytest.approx(0.0)
        assert result[0].bbox.width == pytest.approx(1600.0)
        assert result[0].bbox.height == pytest.approx(1200.0)

    def test_returns_all_detections_unfiltered(self) -> None:
        """_parse_detections returns all regions; filtering is done elsewhere."""
        raw = np.array(
            [
                [6, 0.9, 100.0, 50.0, 400.0, 100.0, 0.0, 0.0],
                [22, 0.1, 200.0, 100.0, 600.0, 300.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        page = _make_page_image()
        result = _parse_detections(raw, page)
        assert len(result) == 2

    def test_unknown_label_for_unmapped_index(self) -> None:
        """Unmapped label index defaults to UNKNOWN."""
        raw = np.array(
            [[99, 0.8, 10.0, 10.0, 100.0, 100.0, 0.0, 0.0]],
            dtype=np.float32,
        )
        page = _make_page_image()
        result = _parse_detections(raw, page)
        assert len(result) == 1
        assert result[0].label == RegionLabel.UNKNOWN

    def test_region_id_format(self) -> None:
        """region_id follows page{N}_region{M} format."""
        raw = np.array(
            [
                [6, 0.9, 10.0, 10.0, 100.0, 50.0, 0.0, 0.0],
                [22, 0.8, 10.0, 60.0, 100.0, 100.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        page = _make_page_image(page_number=3)
        result = _parse_detections(raw, page)
        assert result[0].region_id == "page3_region0"
        assert result[1].region_id == "page3_region1"

    def test_bbox_width_height_non_negative(self) -> None:
        """Width and height are clamped to non-negative values."""
        raw = np.array(
            [[22, 0.9, 400.0, 300.0, 100.0, 100.0, 0.0, 0.0]],
            dtype=np.float32,
        )
        page = _make_page_image()
        result = _parse_detections(raw, page)
        assert result[0].bbox.width >= 0
        assert result[0].bbox.height >= 0

    def test_invalid_shape_wrong_ndim(self) -> None:
        """3D input raises ValueError."""
        raw = np.zeros((1, 8, 1), dtype=np.float32)
        page = _make_page_image()
        with pytest.raises(ValueError, match="Expected model output shape"):
            _parse_detections(raw, page)

    def test_invalid_shape_too_few_columns(self) -> None:
        """Input with < 6 columns raises ValueError."""
        raw = np.array([[1.0, 2.0, 3.0]], dtype=np.float32).reshape(1, 3)
        page = _make_page_image()
        with pytest.raises(ValueError, match="Expected model output shape"):
            _parse_detections(raw, page)


class TestFilterLowConfidence:
    """Tests for _filter_low_confidence()."""

    def test_filters_below_threshold(self) -> None:
        """Only regions above threshold are kept."""
        regions = [
            LayoutRegion(
                bbox=BoundingBox(x=0, y=0, width=100, height=50),
                label=RegionLabel.TITLE,
                confidence=0.9,
                region_id="r1",
            ),
            LayoutRegion(
                bbox=BoundingBox(x=0, y=0, width=100, height=50),
                label=RegionLabel.BODY_TEXT,
                confidence=0.3,
                region_id="r2",
            ),
        ]
        result = _filter_low_confidence(regions, threshold=0.5)
        assert len(result) == 1
        assert result[0].region_id == "r1"

    def test_returns_tuple(self) -> None:
        """Returns an immutable tuple."""
        result = _filter_low_confidence([], 0.5)
        assert isinstance(result, tuple)

    def test_custom_threshold(self) -> None:
        """Custom threshold works correctly."""
        regions = [
            LayoutRegion(
                bbox=BoundingBox(x=0, y=0, width=100, height=50),
                label=RegionLabel.TITLE,
                confidence=0.6,
                region_id="r1",
            ),
        ]
        assert len(_filter_low_confidence(regions, 0.5)) == 1
        assert len(_filter_low_confidence(regions, 0.7)) == 0

    def test_boundary_confidence_exactly_at_threshold(self) -> None:
        """Region with confidence exactly equal to threshold is kept (>=)."""
        regions = [
            LayoutRegion(
                bbox=BoundingBox(x=0, y=0, width=100, height=50),
                label=RegionLabel.TITLE,
                confidence=0.5,
                region_id="r1",
            ),
        ]
        result = _filter_low_confidence(regions, threshold=0.5)
        assert len(result) == 1


class TestDetectLayout:
    """Tests for detect_layout() integration."""

    def test_empty_detections(self) -> None:
        """Page with no detections returns empty LayoutResult."""
        page = _make_page_image()
        session = _make_mock_session(np.zeros((0, 8), dtype=np.float32))
        result = detect_layout(page, session)
        assert isinstance(result, LayoutResult)
        assert result.page_number == 0
        assert result.regions == ()

    def test_multiple_detections_sorted_by_confidence(self) -> None:
        """Multiple detections are sorted by confidence descending."""
        raw = np.array(
            [
                [22, 0.7, 10.0, 10.0, 200.0, 100.0, 0.0, 0.0],
                [6, 0.95, 10.0, 110.0, 200.0, 150.0, 0.0, 0.0],
                [21, 0.8, 210.0, 10.0, 790.0, 200.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        page = _make_page_image()
        session = _make_mock_session(raw)
        result = detect_layout(page, session)
        assert len(result.regions) == 3
        assert result.regions[0].confidence == pytest.approx(0.95)
        assert result.regions[1].confidence == pytest.approx(0.8)
        assert result.regions[2].confidence == pytest.approx(0.7)

    def test_page_number_preserved(self) -> None:
        """Page number from PageImage is preserved in LayoutResult."""
        page = _make_page_image(page_number=5)
        session = _make_mock_session()
        result = detect_layout(page, session)
        assert result.page_number == 5

    def test_result_is_frozen(self) -> None:
        """LayoutResult is immutable."""
        page = _make_page_image()
        session = _make_mock_session()
        result = detect_layout(page, session)
        with pytest.raises(AttributeError):
            result.page_number = 99  # type: ignore[misc]

    def test_custom_confidence_threshold(self) -> None:
        """Custom confidence threshold filters correctly."""
        raw = np.array(
            [
                [6, 0.6, 10.0, 10.0, 200.0, 100.0, 0.0, 0.0],
                [22, 0.4, 10.0, 110.0, 200.0, 150.0, 0.0, 0.0],
            ],
            dtype=np.float32,
        )
        page = _make_page_image()
        session = _make_mock_session(raw)

        result_normal = detect_layout(page, session, confidence_threshold=0.5)
        assert len(result_normal.regions) == 1

        result_strict = detect_layout(page, session, confidence_threshold=0.7)
        assert len(result_strict.regions) == 0

    def test_session_run_called_with_correct_shape(self) -> None:
        """InferenceSession.run is called with correct input shape."""
        page = _make_page_image()
        session = _make_mock_session(np.zeros((0, 8), dtype=np.float32))
        detect_layout(page, session)
        session.run.assert_called_once()
        feeds = session.run.call_args[0][1]
        assert feeds["image"].shape == (1, 3, 800, 800)

    def test_inference_runtime_error(self) -> None:
        """ONNX Runtime errors during inference are wrapped in RuntimeError."""
        page = _make_page_image()
        session = _make_mock_session()
        session.run.side_effect = RuntimeError("ONNX: internal error")
        with pytest.raises(RuntimeError, match="Layout detection inference failed"):
            detect_layout(page, session)
