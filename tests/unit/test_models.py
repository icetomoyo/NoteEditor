"""Tests for noteeditor.models.page module."""

from __future__ import annotations

import numpy as np
import pytest

from noteeditor.models.page import BoundingBox, EmbeddedResource, PageImage, PageMetadata


class TestBoundingBox:
    def test_create_bounding_box(self) -> None:
        bbox = BoundingBox(x=10.0, y=20.0, width=100.0, height=50.0)
        assert bbox.x == 10.0
        assert bbox.y == 20.0
        assert bbox.width == 100.0
        assert bbox.height == 50.0

    def test_bounding_box_is_immutable(self) -> None:
        bbox = BoundingBox(x=0.0, y=0.0, width=100.0, height=100.0)
        with pytest.raises(AttributeError):
            bbox.x = 50.0  # type: ignore[misc]


class TestPageMetadata:
    def test_create_page_metadata(self) -> None:
        meta = PageMetadata(
            page_number=0,
            width_px=1920,
            height_px=1080,
            aspect_ratio=16 / 9,
            total_pages=10,
        )
        assert meta.page_number == 0
        assert meta.width_px == 1920
        assert meta.height_px == 1080
        assert abs(meta.aspect_ratio - 1.778) < 0.001
        assert meta.total_pages == 10

    def test_page_metadata_is_immutable(self) -> None:
        meta = PageMetadata(
            page_number=0,
            width_px=1920,
            height_px=1080,
            aspect_ratio=16 / 9,
            total_pages=10,
        )
        with pytest.raises(AttributeError):
            meta.page_number = 1  # type: ignore[misc]


class TestPageImage:
    def test_create_page_image(self) -> None:
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        page = PageImage(
            page_number=0,
            width_px=200,
            height_px=100,
            dpi=300,
            aspect_ratio=2.0,
            image=image,
        )
        assert page.page_number == 0
        assert page.width_px == 200
        assert page.height_px == 100
        assert page.dpi == 300
        assert page.aspect_ratio == 2.0
        assert page.embedded_images == ()

    def test_page_image_with_embedded_resources(self) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        resource_image = np.zeros((50, 50, 3), dtype=np.uint8)
        bbox = BoundingBox(x=10.0, y=10.0, width=50.0, height=50.0)
        resource = EmbeddedResource(
            index=0,
            bbox=bbox,
            image=resource_image,
            width_px=50,
            height_px=50,
        )
        page = PageImage(
            page_number=1,
            width_px=100,
            height_px=100,
            dpi=150,
            aspect_ratio=1.0,
            image=image,
            embedded_images=(resource,),
        )
        assert len(page.embedded_images) == 1
        assert page.embedded_images[0].index == 0

    def test_page_image_is_immutable(self) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        page = PageImage(
            page_number=0,
            width_px=100,
            height_px=100,
            dpi=300,
            aspect_ratio=1.0,
            image=image,
        )
        with pytest.raises(AttributeError):
            page.page_number = 1  # type: ignore[misc]
