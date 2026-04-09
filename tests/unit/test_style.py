"""Tests for text style estimation stage."""

from __future__ import annotations

import numpy as np

from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage
from noteeditor.stages.style import _estimate_font_size, _sample_font_color, estimate_styles

# --- Helpers ---


def _make_page_image(
    image: np.ndarray | None = None,
    width_px: int = 1000,
    height_px: int = 800,
    dpi: int = 300,
) -> PageImage:
    if image is None:
        image = np.ones((height_px, width_px, 3), dtype=np.uint8) * 255
    return PageImage(
        page_number=0,
        width_px=image.shape[1],
        height_px=image.shape[0],
        dpi=dpi,
        aspect_ratio=image.shape[1] / image.shape[0],
        image=image,
    )


def _make_region(
    region_id: str = "r0",
    label: RegionLabel = RegionLabel.TITLE,
    x: float = 100,
    y: float = 50,
    width: float = 300,
    height: float = 60,
) -> LayoutRegion:
    return LayoutRegion(
        bbox=BoundingBox(x=x, y=y, width=width, height=height),
        label=label,
        confidence=0.9,
        region_id=region_id,
    )


def _make_layout(regions: tuple[LayoutRegion, ...] = ()) -> LayoutResult:
    return LayoutResult(page_number=0, regions=regions)


def _make_image_with_text_color(
    width: int = 1000,
    height: int = 800,
    bbox: BoundingBox | None = None,
    text_color: tuple[int, int, int] = (0, 0, 0),
    bg_color: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """Create image with text-colored region in bbox top-center."""
    image = np.full((height, width, 3), bg_color, dtype=np.uint8)
    if bbox is not None:
        # Fill top 1/3 of bbox, middle 80% width with text color
        top_y = int(bbox.y)
        bot_y = int(bbox.y + bbox.height * 0.33)
        left_x = int(bbox.x + bbox.width * 0.1)
        right_x = int(bbox.x + bbox.width * 0.9)
        top_y = max(0, top_y)
        bot_y = min(height, bot_y)
        left_x = max(0, left_x)
        right_x = min(width, right_x)
        image[top_y:bot_y, left_x:right_x] = text_color
    return image


# --- _estimate_font_size ---


class TestEstimateFontSize:
    def test_basic_estimation(self) -> None:
        result = _estimate_font_size(60.0, 300)
        assert result == 11  # 60 * 72/300 * 0.8 = 11.52 → 11

    def test_returns_integer(self) -> None:
        result = _estimate_font_size(100.0, 300)
        assert isinstance(result, int)

    def test_minimum_font_size(self) -> None:
        result = _estimate_font_size(0.5, 300)
        assert result >= 1

    def test_zero_height_returns_minimum(self) -> None:
        result = _estimate_font_size(0.0, 300)
        assert result >= 1

    def test_higher_dpi_smaller_font(self) -> None:
        at_150 = _estimate_font_size(60.0, 150)
        at_300 = _estimate_font_size(60.0, 300)
        assert at_150 > at_300

    def test_large_title(self) -> None:
        result = _estimate_font_size(120.0, 300)
        assert result == 23  # 120 * 72/300 * 0.8 = 23.04 → 23


# --- _sample_font_color ---


class TestSampleFontColor:
    def test_black_text_on_white(self) -> None:
        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = _make_image_with_text_color(bbox=bbox, text_color=(0, 0, 0))

        result = _sample_font_color(image, bbox)

        assert result == (0, 0, 0)

    def test_colored_text(self) -> None:
        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = _make_image_with_text_color(bbox=bbox, text_color=(255, 0, 0))

        result = _sample_font_color(image, bbox)

        assert result[0] > 200  # Red channel dominant

    def test_white_bg_returns_black_fallback(self) -> None:
        """All-white image returns black as fallback."""
        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = np.ones((800, 1000, 3), dtype=np.uint8) * 255

        result = _sample_font_color(image, bbox)

        assert result == (0, 0, 0)

    def test_bbox_outside_image_clamps(self) -> None:
        """Bbox partially outside image doesn't crash."""
        bbox = BoundingBox(x=-50, y=-10, width=200, height=60)
        image = np.ones((800, 1000, 3), dtype=np.uint8) * 128

        result = _sample_font_color(image, bbox)

        assert len(result) == 3
        assert all(0 <= c <= 255 for c in result)

    def test_preserves_rgb_order(self) -> None:
        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = _make_image_with_text_color(bbox=bbox, text_color=(0, 128, 255))

        result = _sample_font_color(image, bbox)

        assert result[0] < result[1] < result[2]


# --- estimate_styles ---


class TestEstimateStyles:
    def test_returns_text_style_for_text_regions(self) -> None:
        from noteeditor.models.content import TextStyle

        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = _make_image_with_text_color(bbox=bbox, text_color=(0, 0, 0))
        page = _make_page_image(image=image)
        layout = _make_layout((
            _make_region("r0", RegionLabel.TITLE, x=100, y=50, width=300, height=60),
            _make_region("r1", RegionLabel.BODY_TEXT, x=100, y=150, width=400, height=40),
        ))

        result = estimate_styles(page, layout)

        assert len(result) == 2
        assert all(isinstance(s, TextStyle) for s in result)

    def test_skips_non_text_regions(self) -> None:
        page = _make_page_image()
        layout = _make_layout((
            _make_region("r0", RegionLabel.IMAGE),
            _make_region("r1", RegionLabel.TABLE),
            _make_region("r2", RegionLabel.TITLE),
        ))

        result = estimate_styles(page, layout)

        assert len(result) == 1
        assert result[0].region_id == "r2"

    def test_empty_layout(self) -> None:
        page = _make_page_image()
        layout = _make_layout()

        result = estimate_styles(page, layout)

        assert result == ()

    def test_font_size_from_bbox(self) -> None:
        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = _make_image_with_text_color(bbox=bbox, text_color=(0, 0, 0))
        page = _make_page_image(image=image)
        layout = _make_layout((
            _make_region("r0", RegionLabel.TITLE, x=100, y=50, width=300, height=60),
        ))

        result = estimate_styles(page, layout)

        assert result[0].font_size_pt == 11  # 60 * 72/300 * 0.8

    def test_font_color_sampled(self) -> None:
        bbox = BoundingBox(x=100, y=50, width=300, height=60)
        image = _make_image_with_text_color(bbox=bbox, text_color=(0, 0, 255))
        page = _make_page_image(image=image)
        layout = _make_layout((
            _make_region("r0", RegionLabel.TITLE, x=100, y=50, width=300, height=60),
        ))

        result = estimate_styles(page, layout)

        assert result[0].font_color_rgb[2] > 200  # Blue dominant

    def test_preserves_region_id(self) -> None:
        page = _make_page_image()
        layout = _make_layout((
            _make_region("my_region_42", RegionLabel.BODY_TEXT),
        ))

        result = estimate_styles(page, layout)

        assert result[0].region_id == "my_region_42"

    def test_equation_included(self) -> None:
        page = _make_page_image()
        layout = _make_layout((
            _make_region("r0", RegionLabel.EQUATION),
        ))

        result = estimate_styles(page, layout)

        assert len(result) == 1
