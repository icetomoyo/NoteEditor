"""Tests for stages/background.py - Background extraction (Feature 013)."""

from __future__ import annotations

import numpy as np

from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import PageImage
from noteeditor.stages.background import (
    _classify_background,
    _create_text_mask,
    _fill_fallback,
    _fill_gradient,
    _fill_simple,
    extract_background,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_page_image(
    image: np.ndarray | None = None,
    page_number: int = 0,
) -> PageImage:
    """Create a PageImage with given or synthetic image."""
    if image is None:
        image = np.ones((400, 600, 3), dtype=np.uint8) * 200
    h, w = image.shape[:2]
    return PageImage(
        page_number=page_number,
        width_px=w,
        height_px=h,
        dpi=300,
        aspect_ratio=w / h if h > 0 else 1.0,
        image=image,
    )


def _make_region(
    label: RegionLabel = RegionLabel.BODY_TEXT,
    x: float = 50.0,
    y: float = 50.0,
    width: float = 200.0,
    height: float = 40.0,
    region_id: str = "page0_region0",
) -> LayoutRegion:
    """Create a LayoutRegion."""
    return LayoutRegion(
        bbox=BoundingBox(x=x, y=y, width=width, height=height),
        label=label,
        confidence=0.9,
        region_id=region_id,
    )


def _make_layout_result(
    regions: tuple[LayoutRegion, ...] = (),
    page_number: int = 0,
) -> LayoutResult:
    """Create a LayoutResult."""
    return LayoutResult(page_number=page_number, regions=regions)


# ---------------------------------------------------------------------------
# _create_text_mask
# ---------------------------------------------------------------------------


class TestCreateTextMask:
    """Tests for _create_text_mask."""

    def test_empty_regions_returns_all_zeros(self) -> None:
        """No regions → all-zero mask."""
        mask = _create_text_mask((400, 600), ())
        assert mask.shape == (400, 600)
        assert mask.dtype == np.uint8
        assert mask.max() == 0

    def test_text_region_marked(self) -> None:
        """Text region bbox is marked as 255 in mask."""
        region = _make_region(x=10, y=20, width=50, height=30)
        mask = _create_text_mask((400, 600), (region,))
        assert mask[20:50, 10:60].max() == 255

    def test_image_region_not_marked(self) -> None:
        """IMAGE label regions are not in the mask."""
        region = _make_region(label=RegionLabel.IMAGE, x=10, y=20, width=50, height=30)
        mask = _create_text_mask((400, 600), (region,))
        assert mask[20:50, 10:60].max() == 0

    def test_multiple_text_regions(self) -> None:
        """Multiple text regions all marked."""
        r1 = _make_region(x=0, y=0, width=100, height=20, region_id="r1")
        r2 = _make_region(x=0, y=30, width=100, height=20, region_id="r2")
        mask = _create_text_mask((400, 600), (r1, r2))
        assert mask[0:20, 0:100].max() == 255
        assert mask[30:50, 0:100].max() == 255

    def test_bbox_clamped_to_image(self) -> None:
        """Bbox extending beyond image bounds is clamped."""
        region = _make_region(x=590, y=390, width=100, height=100)
        mask = _create_text_mask((400, 600), (region,))
        assert mask.shape == (400, 600)
        # Should not crash, clamped region should be marked
        assert mask[390:400, 590:600].max() == 255

    def test_title_included(self) -> None:
        """TITLE regions are included in text mask."""
        region = _make_region(label=RegionLabel.TITLE, x=10, y=10, width=100, height=30)
        mask = _create_text_mask((400, 600), (region,))
        assert mask[10:40, 10:110].max() == 255

    def test_equation_included(self) -> None:
        """EQUATION regions are included in text mask."""
        region = _make_region(label=RegionLabel.EQUATION, x=10, y=10, width=100, height=30)
        mask = _create_text_mask((400, 600), (region,))
        assert mask[10:40, 10:110].max() == 255

    def test_table_not_included(self) -> None:
        """TABLE regions are not included in text mask."""
        region = _make_region(label=RegionLabel.TABLE, x=10, y=10, width=100, height=30)
        mask = _create_text_mask((400, 600), (region,))
        assert mask[10:40, 10:110].max() == 0


# ---------------------------------------------------------------------------
# _classify_background
# ---------------------------------------------------------------------------


class TestClassifyBackground:
    """Tests for _classify_background."""

    def test_uniform_background_is_simple(self) -> None:
        """Uniform color background → 'simple'."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 200
        mask = np.zeros((100, 100), dtype=np.uint8)
        assert _classify_background(image, mask) == "simple"

    def test_near_uniform_is_simple(self) -> None:
        """Near-uniform (low noise) background → 'simple'."""
        rng = np.random.default_rng(42)
        image = np.ones((100, 100, 3), dtype=np.uint8) * 200
        image = np.clip(image + rng.integers(-5, 6, image.shape), 0, 255).astype(np.uint8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        assert _classify_background(image, mask) == "simple"

    def test_gradient_is_gradient(self) -> None:
        """Gradient background → 'gradient'."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        for x in range(100):
            image[:, x] = int(x * 0.8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        result = _classify_background(image, mask)
        assert result == "gradient"

    def test_noisy_is_complex(self) -> None:
        """High variance background → 'complex'."""
        rng = np.random.default_rng(42)
        image = rng.integers(0, 256, (100, 100, 3), dtype=np.uint8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        result = _classify_background(image, mask)
        assert result == "complex"

    def test_masked_region_excluded(self) -> None:
        """Masked (text) regions are excluded from classification."""
        # Uniform background with one noisy text region
        image = np.ones((100, 100, 3), dtype=np.uint8) * 200
        rng = np.random.default_rng(42)
        image[40:60, 40:60] = rng.integers(0, 256, (20, 20, 3), dtype=np.uint8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        # Without mask → complex; with mask → simple
        assert _classify_background(image, mask) == "simple"


# ---------------------------------------------------------------------------
# _fill_simple
# ---------------------------------------------------------------------------


class TestFillSimple:
    """Tests for _fill_simple."""

    def test_fills_with_median_color(self) -> None:
        """Masked regions filled with median background color."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 180
        image[40:60, 40:60] = 0  # Text region
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255

        result = _fill_simple(image, mask)
        assert result[50, 50, 0] == 180

    def test_preserves_background(self) -> None:
        """Non-masked regions are unchanged."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 180
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255

        result = _fill_simple(image, mask)
        np.testing.assert_array_equal(result[10, 10], [180, 180, 180])

    def test_returns_new_array(self) -> None:
        """Does not mutate the input image."""
        image = np.ones((100, 100, 3), dtype=np.uint8) * 180
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        original = image.copy()

        _fill_simple(image, mask)
        np.testing.assert_array_equal(image, original)


# ---------------------------------------------------------------------------
# _fill_gradient
# ---------------------------------------------------------------------------


class TestFillGradient:
    """Tests for _fill_gradient."""

    def test_fills_with_interpolated_values(self) -> None:
        """Masked regions filled with per-row interpolated colors."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Left=100, Right=200 horizontal gradient
        for x in range(100):
            image[:, x] = int(100 + x)
        # Mask center region
        image[40:60, 40:60] = 0
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255

        result = _fill_gradient(image, mask)
        # Center pixel (row 50, col 50) should be between left(150) and right(150)
        # Both sides are same at x=50, so should be ~150
        assert result[50, 50, 0] > 100
        assert result[50, 50, 0] < 255

    def test_preserves_unmasked(self) -> None:
        """Non-masked regions are unchanged."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        for x in range(100):
            image[:, x] = int(100 + x)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255

        result = _fill_gradient(image, mask)
        assert result[10, 10, 0] == 110

    def test_returns_new_array(self) -> None:
        """Does not mutate input."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        for x in range(100):
            image[:, x] = int(100 + x)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        original = image.copy()

        _fill_gradient(image, mask)
        np.testing.assert_array_equal(image, original)


# ---------------------------------------------------------------------------
# _fill_fallback
# ---------------------------------------------------------------------------


class TestFillFallback:
    """Tests for _fill_fallback."""

    def test_fills_with_white(self) -> None:
        """Masked regions filled with white."""
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255

        result = _fill_fallback(image, mask)
        assert result[50, 50, 0] == 255
        assert result[50, 50, 1] == 255
        assert result[50, 50, 2] == 255


# ---------------------------------------------------------------------------
# extract_background (integration)
# ---------------------------------------------------------------------------


class TestExtractBackground:
    """Tests for extract_background (end-to-end)."""

    def test_simple_background(self) -> None:
        """Simple background: text regions filled with background color."""
        image = np.ones((400, 600, 3), dtype=np.uint8) * 200
        # Simulate dark text on light background
        image[50:90, 50:250] = 50

        page = _make_page_image(image)
        region = _make_region(x=50, y=50, width=200, height=40)
        layout = _make_layout_result(regions=(region,))

        result = extract_background(page, layout)
        # Text region should now be background color
        assert result[70, 150, 0] == 200

    def test_no_text_regions_returns_original(self) -> None:
        """No text regions → return unmodified image."""
        image = np.ones((400, 600, 3), dtype=np.uint8) * 200
        page = _make_page_image(image)
        layout = _make_layout_result(regions=())

        result = extract_background(page, layout)
        np.testing.assert_array_equal(result, image)

    def test_preserves_non_text_regions(self) -> None:
        """IMAGE regions are not removed from background."""
        image = np.ones((400, 600, 3), dtype=np.uint8) * 200
        # Draw a colored image region
        image[100:200, 100:300] = [255, 0, 0]

        page = _make_page_image(image)
        img_region = _make_region(
            label=RegionLabel.IMAGE, x=100, y=100, width=200, height=100,
        )
        layout = _make_layout_result(regions=(img_region,))

        result = extract_background(page, layout)
        # Image region should be preserved
        assert result[150, 200, 0] == 255

    def test_output_shape_matches_input(self) -> None:
        """Output image has same shape as input."""
        image = np.ones((300, 500, 3), dtype=np.uint8) * 200
        page = _make_page_image(image)
        layout = _make_layout_result(regions=(_make_region(),))

        result = extract_background(page, layout)
        assert result.shape == image.shape

    def test_does_not_modify_input(self) -> None:
        """Input PageImage.image is not mutated."""
        image = np.ones((400, 600, 3), dtype=np.uint8) * 200
        image[50:90, 50:250] = 50
        original = image.copy()

        page = _make_page_image(image)
        region = _make_region(x=50, y=50, width=200, height=40)
        layout = _make_layout_result(regions=(region,))

        extract_background(page, layout)
        np.testing.assert_array_equal(page.image, original)

    def test_complex_background_fallback_no_lama(self) -> None:
        """Complex background falls back to white fill when no LaMA."""
        rng = np.random.default_rng(42)
        image = rng.integers(0, 256, (400, 600, 3), dtype=np.uint8)
        image[50:90, 50:250] = 0

        page = _make_page_image(image)
        region = _make_region(x=50, y=50, width=200, height=40)
        layout = _make_layout_result(regions=(region,))

        result = extract_background(page, layout, lama_session=None)
        # Should fill with white (fallback)
        assert result[70, 150, 0] == 255

    def test_complex_background_lama_failure_fallback(self) -> None:
        """LaMA inference failure falls back to white fill."""
        from unittest.mock import MagicMock

        rng = np.random.default_rng(42)
        image = rng.integers(0, 256, (400, 600, 3), dtype=np.uint8)
        image[50:90, 50:250] = 0

        mock_session = MagicMock()
        mock_session.run.side_effect = RuntimeError("ONNX error")
        mock_session.get_inputs.return_value = [MagicMock(name="image"), MagicMock(name="mask")]

        page = _make_page_image(image)
        region = _make_region(x=50, y=50, width=200, height=40)
        layout = _make_layout_result(regions=(region,))

        result = extract_background(page, layout, lama_session=mock_session)
        # Should fall back to white fill
        assert result[70, 150, 0] == 255

    def test_multiple_text_and_image_regions(self) -> None:
        """Mixed text and image regions: text filled, image preserved."""
        image = np.ones((400, 600, 3), dtype=np.uint8) * 200
        image[50:90, 50:250] = 50  # text
        image[100:200, 100:300] = [255, 0, 0]  # image

        page = _make_page_image(image)
        text_region = _make_region(
            x=50, y=50, width=200, height=40, region_id="r1",
        )
        img_region = _make_region(
            label=RegionLabel.IMAGE, x=100, y=100, width=200, height=100,
            region_id="r2",
        )
        layout = _make_layout_result(regions=(text_region, img_region))

        result = extract_background(page, layout)
        # Text region filled with background
        assert result[70, 150, 0] == 200
        # Image region preserved
        assert result[150, 200, 0] == 255
