"""Tests for stages/ocr.py - OCR text extraction via Backend."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from noteeditor.infra.ocr_backend import OCRResponse
from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage
from noteeditor.stages.ocr import (
    _crop_region,
    _filter_text_regions,
    extract_text,
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


def _make_mock_backend(
    responses: list[OCRResponse] | None = None,
) -> MagicMock:
    """Create a mock OCRBackend.

    Each call to recognize() returns the next response in sequence.
    """
    backend = MagicMock()
    backend.is_available.return_value = True
    if responses:
        backend.recognize.side_effect = responses
    else:
        backend.recognize.return_value = OCRResponse(
            text="", is_formula=False, formula_latex=None, raw_output="",
        )
    return backend


class TestFilterTextRegions:
    """Tests for _filter_text_regions()."""

    def test_keeps_body_text(self) -> None:
        region = _make_text_region(label=RegionLabel.BODY_TEXT)
        result = _filter_text_regions((region,))
        assert len(result) == 1
        assert result[0].label == RegionLabel.BODY_TEXT

    def test_keeps_title(self) -> None:
        region = _make_text_region(label=RegionLabel.TITLE)
        result = _filter_text_regions((region,))
        assert len(result) == 1

    def test_keeps_equation(self) -> None:
        region = _make_text_region(label=RegionLabel.EQUATION)
        result = _filter_text_regions((region,))
        assert len(result) == 1

    def test_keeps_code_block(self) -> None:
        region = _make_text_region(label=RegionLabel.CODE_BLOCK)
        result = _filter_text_regions((region,))
        assert len(result) == 1

    def test_filters_image(self) -> None:
        region = _make_text_region(label=RegionLabel.IMAGE)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_table(self) -> None:
        region = _make_text_region(label=RegionLabel.TABLE)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_header_footer(self) -> None:
        regions = (
            _make_text_region(label=RegionLabel.HEADER),
            _make_text_region(label=RegionLabel.FOOTER),
        )
        result = _filter_text_regions(regions)
        assert len(result) == 0

    def test_filters_figure_caption(self) -> None:
        region = _make_text_region(label=RegionLabel.FIGURE_CAPTION)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_reference(self) -> None:
        region = _make_text_region(label=RegionLabel.REFERENCE)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_filters_unknown(self) -> None:
        region = _make_text_region(label=RegionLabel.UNKNOWN)
        result = _filter_text_regions((region,))
        assert len(result) == 0

    def test_mixed_regions(self) -> None:
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
        result = _filter_text_regions(())
        assert result == ()
        assert isinstance(result, tuple)

    def test_returns_tuple(self) -> None:
        region = _make_text_region()
        result = _filter_text_regions((region,))
        assert isinstance(result, tuple)


class TestCropRegion:
    """Tests for _crop_region()."""

    def test_basic_crop(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        image[100:130, 200:400] = 255
        bbox = BoundingBox(x=200.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.shape == (30, 200, 3)
        assert np.all(cropped == 255)

    def test_padding_applied(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape == (50, 220, 3)

    def test_custom_padding(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=20)
        assert cropped.shape == (70, 240, 3)

    def test_clamp_at_top_boundary(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=0.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[0] == 40
        assert cropped.shape[1] == 220

    def test_clamp_at_left_boundary(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=0.0, y=100.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[1] == 210

    def test_clamp_at_right_boundary(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=750.0, y=100.0, width=50.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[1] == 60

    def test_clamp_at_bottom_boundary(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=200.0, y=570.0, width=200.0, height=30.0)
        cropped = _crop_region(image, bbox, padding=10)
        assert cropped.shape[0] == 40

    def test_clamp_all_boundaries(self) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = BoundingBox(x=-50.0, y=-50.0, width=200.0, height=200.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.shape == (100, 100, 3)

    def test_output_is_view(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=100.0, y=100.0, width=50.0, height=50.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.shape == (50, 50, 3)
        assert cropped.base is image

    def test_output_dtype(self) -> None:
        image = np.zeros((600, 800, 3), dtype=np.uint8)
        bbox = BoundingBox(x=100.0, y=100.0, width=50.0, height=50.0)
        cropped = _crop_region(image, bbox, padding=0)
        assert cropped.dtype == np.uint8


class TestExtractText:
    """Tests for extract_text() - OCR Backend mode."""

    def test_no_text_regions(self) -> None:
        page = _make_page_image()
        layout = _make_layout_result(regions=[])
        backend = _make_mock_backend()
        result = extract_text(page, layout, backend)
        assert result == ()

    def test_non_text_regions_skipped(self) -> None:
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.IMAGE),
            _make_text_region(region_id="r2", label=RegionLabel.TABLE),
        ]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend()
        result = extract_text(page, layout, backend)
        assert result == ()
        backend.recognize.assert_not_called()

    def test_single_text_region(self) -> None:
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="page0_region0", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend([
            OCRResponse(
                text="Hello World", is_formula=False,
                formula_latex=None, raw_output="Hello World",
            ),
        ])
        result = extract_text(page, layout, backend)
        assert len(result) == 1
        assert result[0].text == "Hello World"
        assert result[0].is_formula is False
        assert result[0].region_id == "page0_region0"

    def test_multiple_text_regions(self) -> None:
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.TITLE),
            _make_text_region(region_id="r2", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend([
            OCRResponse(
                text="Title", is_formula=False,
                formula_latex=None, raw_output="Title",
            ),
            OCRResponse(
                text="Body text", is_formula=False,
                formula_latex=None, raw_output="Body text",
            ),
        ])
        result = extract_text(page, layout, backend)
        assert len(result) == 2
        assert result[0].text == "Title"
        assert result[1].text == "Body text"

    def test_formula_region(self) -> None:
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="eq1", label=RegionLabel.EQUATION),
        ]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend([
            OCRResponse(
                text="a^2+b^2=c^2", is_formula=True,
                formula_latex="a^2+b^2=c^2", raw_output="",
            ),
        ])
        result = extract_text(page, layout, backend)
        assert len(result) == 1
        assert result[0].is_formula is True
        assert result[0].formula_latex == "a^2+b^2=c^2"

    def test_mixed_regions_only_text_processed(self) -> None:
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.TITLE),
            _make_text_region(region_id="r2", label=RegionLabel.IMAGE),
            _make_text_region(region_id="r3", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend([
            OCRResponse(text="Title", is_formula=False, formula_latex=None, raw_output=""),
            OCRResponse(text="Body", is_formula=False, formula_latex=None, raw_output=""),
        ])
        result = extract_text(page, layout, backend)
        assert len(result) == 2

    def test_returns_tuple(self) -> None:
        page = _make_page_image()
        layout = _make_layout_result()
        backend = _make_mock_backend()
        result = extract_text(page, layout, backend)
        assert isinstance(result, tuple)

    def test_backend_error_wrapped(self) -> None:
        """Backend errors are wrapped in RuntimeError with page context."""
        page = _make_page_image(page_number=3)
        regions = [_make_text_region(label=RegionLabel.BODY_TEXT)]
        layout = _make_layout_result(regions=regions)
        backend = MagicMock()
        backend.recognize.side_effect = RuntimeError("backend: connection refused")
        with pytest.raises(RuntimeError, match="OCR failed for page 3"):
            extract_text(page, layout, backend)

    def test_empty_text_skipped(self) -> None:
        """Regions where OCR returns empty text are skipped."""
        page = _make_page_image()
        regions = [
            _make_text_region(region_id="r1", label=RegionLabel.BODY_TEXT),
            _make_text_region(region_id="r2", label=RegionLabel.BODY_TEXT),
        ]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend([
            OCRResponse(text="", is_formula=False, formula_latex=None, raw_output=""),
            OCRResponse(text="Real text", is_formula=False, formula_latex=None, raw_output=""),
        ])
        result = extract_text(page, layout, backend)
        assert len(result) == 1
        assert result[0].text == "Real text"

    def test_equation_task_prompt(self) -> None:
        """EQUATION regions should use 'Formula Recognition:' task prompt."""
        page = _make_page_image()
        regions = [_make_text_region(region_id="eq1", label=RegionLabel.EQUATION)]
        layout = _make_layout_result(regions=regions)
        backend = _make_mock_backend([
            OCRResponse(text="x^2", is_formula=True, formula_latex="x^2", raw_output=""),
        ])
        extract_text(page, layout, backend)
        call_args = backend.recognize.call_args
        assert call_args[0][1] == "Formula Recognition:"
