"""Tests for noteeditor.models.layout module."""

from __future__ import annotations

import pytest

from noteeditor.models.layout import LayoutRegion, LayoutResult, RegionLabel
from noteeditor.models.page import BoundingBox


class TestRegionLabel:
    def test_all_labels_are_strings(self) -> None:
        for label in RegionLabel:
            assert isinstance(label, str)

    def test_expected_labels_exist(self) -> None:
        assert RegionLabel.TITLE == "title"
        assert RegionLabel.BODY_TEXT == "body_text"
        assert RegionLabel.IMAGE == "image"


class TestLayoutRegion:
    def test_create_layout_region(self) -> None:
        bbox = BoundingBox(x=10.0, y=20.0, width=200.0, height=50.0)
        region = LayoutRegion(
            bbox=bbox,
            label=RegionLabel.TITLE,
            confidence=0.95,
            region_id="page0_region0",
        )
        assert region.label == RegionLabel.TITLE
        assert region.confidence == 0.95
        assert region.region_id == "page0_region0"

    def test_layout_region_is_immutable(self) -> None:
        bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0)
        region = LayoutRegion(
            bbox=bbox, label=RegionLabel.UNKNOWN, confidence=0.5, region_id="r1"
        )
        with pytest.raises(AttributeError):
            region.confidence = 1.0  # type: ignore[misc]


class TestLayoutResult:
    def test_create_layout_result(self) -> None:
        bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0)
        regions = (
            LayoutRegion(bbox=bbox, label=RegionLabel.TITLE, confidence=0.9, region_id="r1"),
        )
        result = LayoutResult(page_number=0, regions=regions)
        assert result.page_number == 0
        assert len(result.regions) == 1
