"""Tests for image extraction stage."""

from __future__ import annotations

import numpy as np
import pytest

from noteeditor.models.content import ExtractedImage
from noteeditor.models.layout import LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import BoundingBox, EmbeddedResource, PageImage
from noteeditor.stages.image import (
    _compute_iou,
    _crop_image,
    _filter_image_regions,
    _match_embedded,
    extract_images,
)

# --- Helpers ---


def _make_bbox(
    x: float = 0, y: float = 0, w: float = 100, h: float = 100,
) -> BoundingBox:
    return BoundingBox(x=x, y=y, width=w, height=h)


def _make_region(
    region_id: str = "r0",
    label: RegionLabel = RegionLabel.IMAGE,
    bbox: BoundingBox | None = None,
) -> LayoutRegion:
    return LayoutRegion(
        bbox=bbox or _make_bbox(),
        label=label,
        confidence=0.9,
        region_id=region_id,
    )


def _make_resource(
    index: int = 0,
    bbox: BoundingBox | None = None,
    w: int = 50,
    h: int = 50,
) -> EmbeddedResource:
    return EmbeddedResource(
        index=index,
        bbox=bbox or _make_bbox(),
        image=np.zeros((h, w, 3), dtype=np.uint8),
        width_px=w,
        height_px=h,
    )


def _make_page_image(
    resources: tuple[EmbeddedResource, ...] = (),
    w: int = 800,
    h: int = 600,
) -> PageImage:
    return PageImage(
        page_number=0,
        width_px=w,
        height_px=h,
        dpi=300,
        aspect_ratio=w / h,
        image=np.ones((h, w, 3), dtype=np.uint8) * 128,
        embedded_images=resources,
    )


def _make_layout(regions: tuple[LayoutRegion, ...] = ()) -> LayoutResult:
    return LayoutResult(page_number=0, regions=regions)


# --- _filter_image_regions ---


class TestFilterImageRegions:
    def test_returns_only_image_regions(self) -> None:
        regions = (
            _make_region("r0", RegionLabel.IMAGE),
            _make_region("r1", RegionLabel.TITLE),
            _make_region("r2", RegionLabel.BODY_TEXT),
            _make_region("r3", RegionLabel.IMAGE),
        )
        result = _filter_image_regions(regions)
        assert len(result) == 2
        assert all(r.label == RegionLabel.IMAGE for r in result)

    def test_empty_regions(self) -> None:
        assert _filter_image_regions(()) == ()

    def test_no_image_regions(self) -> None:
        regions = (
            _make_region("r0", RegionLabel.TITLE),
            _make_region("r1", RegionLabel.BODY_TEXT),
        )
        assert _filter_image_regions(regions) == ()


# --- _compute_iou ---


class TestComputeIou:
    def test_perfect_overlap(self) -> None:
        a = _make_bbox(10, 10, 50, 50)
        b = _make_bbox(10, 10, 50, 50)
        assert _compute_iou(a, b) == pytest.approx(1.0)

    def test_no_overlap(self) -> None:
        a = _make_bbox(0, 0, 50, 50)
        b = _make_bbox(100, 100, 50, 50)
        assert _compute_iou(a, b) == pytest.approx(0.0)

    def test_partial_overlap(self) -> None:
        a = _make_bbox(0, 0, 100, 100)
        b = _make_bbox(50, 50, 100, 100)
        # intersection = 50*50 = 2500, union = 10000 + 10000 - 2500 = 17500
        expected = 2500 / 17500
        assert _compute_iou(a, b) == pytest.approx(expected, rel=1e-4)

    def test_one_inside_other(self) -> None:
        a = _make_bbox(0, 0, 100, 100)
        b = _make_bbox(25, 25, 50, 50)
        # intersection = 50*50 = 2500, union = 10000
        expected = 2500 / 10000
        assert _compute_iou(a, b) == pytest.approx(expected, rel=1e-4)

    def test_touching_edges(self) -> None:
        a = _make_bbox(0, 0, 50, 50)
        b = _make_bbox(50, 0, 50, 50)
        # intersection = 0 (touching edge, no overlap area)
        assert _compute_iou(a, b) == pytest.approx(0.0)


# --- _match_embedded ---


class TestMatchEmbedded:
    def test_matches_with_high_iou(self) -> None:
        region = _make_region("r0", bbox=_make_bbox(10, 10, 100, 100))
        resources = (_make_resource(0, bbox=_make_bbox(12, 12, 98, 98)),)
        result = _match_embedded(region, resources)
        assert result is not None
        assert result.index == 0

    def test_no_match_below_threshold(self) -> None:
        region = _make_region("r0", bbox=_make_bbox(0, 0, 50, 50))
        resources = (_make_resource(0, bbox=_make_bbox(200, 200, 50, 50)),)
        result = _match_embedded(region, resources)
        assert result is None

    def test_empty_resources(self) -> None:
        region = _make_region("r0")
        result = _match_embedded(region, ())
        assert result is None

    def test_picks_best_match(self) -> None:
        region = _make_region("r0", bbox=_make_bbox(10, 10, 100, 100))
        resources = (
            _make_resource(0, bbox=_make_bbox(200, 200, 100, 100)),  # no overlap
            _make_resource(1, bbox=_make_bbox(12, 12, 98, 98)),      # high overlap
            _make_resource(2, bbox=_make_bbox(15, 15, 90, 90)),      # also high
        )
        result = _match_embedded(region, resources)
        assert result is not None
        assert result.index == 1  # best match


# --- _crop_image ---


class TestCropImage:
    def test_crops_valid_region(self) -> None:
        image = np.arange(300, dtype=np.uint8).reshape(10, 10, 3)
        bbox = _make_bbox(2, 3, 4, 5)
        result = _crop_image(image, bbox)
        assert result.shape == (5, 4, 3)

    def test_clamps_to_image_bounds(self) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        bbox = _make_bbox(-10, -5, 30, 30)
        result = _crop_image(image, bbox)
        assert result.shape[0] <= 30
        assert result.shape[1] <= 30

    def test_clamps_right_bottom(self) -> None:
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        bbox = _make_bbox(40, 40, 20, 20)
        result = _crop_image(image, bbox)
        assert result.shape == (10, 10, 3)

    def test_returns_copy(self) -> None:
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        bbox = _make_bbox(0, 0, 10, 10)
        result = _crop_image(image, bbox)
        result[0, 0] = 255
        assert image[0, 0, 0] == 0  # original unchanged


# --- extract_images (public) ---


class TestExtractImages:
    def test_no_image_regions(self) -> None:
        page = _make_page_image()
        layout = _make_layout((_make_region("r0", RegionLabel.TITLE),))
        result = extract_images(page, layout)
        assert result == ()

    def test_embedded_resource_matched(self) -> None:
        resource = _make_resource(0, bbox=_make_bbox(100, 100, 200, 150))
        page = _make_page_image(resources=(resource,))
        layout = _make_layout((
            _make_region("img0", bbox=_make_bbox(105, 105, 190, 140)),
        ))
        result = extract_images(page, layout)
        assert len(result) == 1
        assert result[0].source == "embedded"
        assert result[0].region_id == "img0"

    def test_crop_fallback_when_no_embedded(self) -> None:
        page = _make_page_image()
        layout = _make_layout((
            _make_region("img0", bbox=_make_bbox(100, 100, 200, 150)),
        ))
        result = extract_images(page, layout)
        assert len(result) == 1
        assert result[0].source == "cropped"
        assert result[0].region_id == "img0"

    def test_mixed_sources(self) -> None:
        resource = _make_resource(0, bbox=_make_bbox(100, 100, 200, 150))
        page = _make_page_image(resources=(resource,))
        layout = _make_layout((
            _make_region("img0", bbox=_make_bbox(105, 105, 190, 140)),  # matches
            _make_region("img1", bbox=_make_bbox(400, 400, 200, 150)),  # no match
        ))
        result = extract_images(page, layout)
        assert len(result) == 2
        sources = {r.region_id: r.source for r in result}
        assert sources["img0"] == "embedded"
        assert sources["img1"] == "cropped"

    def test_returns_extracted_image_instances(self) -> None:
        page = _make_page_image()
        layout = _make_layout((
            _make_region("img0", bbox=_make_bbox(10, 10, 50, 50)),
        ))
        result = extract_images(page, layout)
        assert len(result) == 1
        img = result[0]
        assert isinstance(img, ExtractedImage)
        assert img.width_px == img.image.shape[1]
        assert img.height_px == img.image.shape[0]
