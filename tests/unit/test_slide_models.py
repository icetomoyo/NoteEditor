"""Tests for noteeditor.models.slide module."""

from __future__ import annotations

import numpy as np

from noteeditor.models.content import FontMatch
from noteeditor.models.layout import RegionLabel
from noteeditor.models.page import BoundingBox
from noteeditor.models.slide import ImageBlock, SlideContent, TextBlock


class TestTextBlock:
    def test_create_text_block(self) -> None:
        bbox = BoundingBox(x=10.0, y=20.0, width=300.0, height=40.0)
        font = FontMatch(
            region_id="page0_region0",
            label=RegionLabel.TITLE,
            font_name="Google Sans",
            font_path=None,
            system_fallback="Arial",
            is_fallback=True,
        )
        block = TextBlock(
            region_id="page0_region0",
            bbox=bbox,
            text="Title Text",
            font_match=font,
            is_formula=False,
        )
        assert block.text == "Title Text"
        assert block.is_formula is False
        assert block.formula_latex is None


class TestImageBlock:
    def test_create_image_block(self) -> None:
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        bbox = BoundingBox(x=50.0, y=100.0, width=200.0, height=100.0)
        block = ImageBlock(
            region_id="page0_region1",
            bbox=bbox,
            image=image,
            source="cropped",
        )
        assert block.source == "cropped"


class TestSlideContent:
    def test_create_slide_content_success(self) -> None:
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        full = np.zeros((100, 100, 3), dtype=np.uint8)
        content = SlideContent(
            page_number=0,
            background_image=bg,
            full_page_image=full,
            text_blocks=(),
            image_blocks=(),
            status="success",
        )
        assert content.status == "success"
        assert content.text_blocks == ()

    def test_slide_content_fallback(self) -> None:
        full = np.zeros((100, 100, 3), dtype=np.uint8)
        content = SlideContent(
            page_number=2,
            background_image=None,
            full_page_image=full,
            text_blocks=(),
            image_blocks=(),
            status="fallback",
        )
        assert content.background_image is None
        assert content.status == "fallback"
