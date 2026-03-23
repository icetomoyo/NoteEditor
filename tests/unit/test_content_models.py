"""Tests for noteeditor.models.content module."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from noteeditor.models.content import ExtractedImage, FontMatch, OCRResult
from noteeditor.models.layout import RegionLabel
from noteeditor.models.page import BoundingBox


class TestOCRResult:
    def test_create_ocr_result(self) -> None:
        result = OCRResult(
            region_id="page0_region0",
            text="Hello World",
            confidence=0.98,
            is_formula=False,
        )
        assert result.text == "Hello World"
        assert result.is_formula is False
        assert result.formula_latex is None

    def test_create_ocr_result_with_formula(self) -> None:
        result = OCRResult(
            region_id="page0_region1",
            text="E=mc^2",
            confidence=0.85,
            is_formula=True,
            formula_latex="E=mc^2",
        )
        assert result.is_formula is True
        assert result.formula_latex == "E=mc^2"


class TestExtractedImage:
    def test_create_extracted_image(self) -> None:
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        bbox = BoundingBox(x=10.0, y=10.0, width=50.0, height=50.0)
        extracted = ExtractedImage(
            region_id="page0_region2",
            image=image,
            source="embedded",
            bbox=bbox,
            width_px=50,
            height_px=50,
        )
        assert extracted.source == "embedded"
        assert extracted.width_px == 50


class TestFontMatch:
    def test_create_font_match_with_path(self) -> None:
        match = FontMatch(
            region_id="page0_region0",
            label=RegionLabel.TITLE,
            font_name="Google Sans",
            font_path=Path("/fonts/GoogleSans-Bold.ttf"),
            system_fallback=None,
            is_fallback=False,
        )
        assert match.font_name == "Google Sans"
        assert match.is_fallback is False

    def test_create_font_match_fallback(self) -> None:
        match = FontMatch(
            region_id="page0_region1",
            label=RegionLabel.BODY_TEXT,
            font_name="Arial",
            font_path=None,
            system_fallback="Arial",
            is_fallback=True,
        )
        assert match.font_path is None
        assert match.is_fallback is True
