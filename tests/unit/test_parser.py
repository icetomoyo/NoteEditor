"""Tests for stages/parser.py - PDF page rendering."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from noteeditor.errors import InputError
from noteeditor.models.page import PageImage
from noteeditor.stages.parser import (
    _extract_embedded_resources,
    parse_pdf,
    pixmap_to_numpy,
    render_page,
)


def _make_mock_pixmap(
    width: int = 100, height: int = 100, n: int = 3
) -> MagicMock:
    """Create a mock Pixmap with realistic attributes.

    PyMuPDF uses both .h/.w (short) and .height/.width (long).
    """
    pixmap = MagicMock()
    pixmap.width = width
    pixmap.height = height
    pixmap.w = width
    pixmap.h = height
    pixmap.n = n
    pixmap.samples = bytes(width * height * n)
    return pixmap


def _make_mock_page(
    width: int = 612, height: int = 792, pixmap: MagicMock | None = None
) -> MagicMock:
    """Create a mock fitz.Page with rect and get_pixmap."""
    page = MagicMock()
    page.rect.width = width
    page.rect.height = height
    page.get_pixmap.return_value = pixmap or _make_mock_pixmap()
    return page


class TestPixmapToNumpy:
    """Tests for pixmap_to_numpy conversion."""

    def test_rgb_pixmap_to_array(self) -> None:
        """RGB pixmap (n=3) produces (H, W, 3) array."""
        pixmap = _make_mock_pixmap(width=20, height=10, n=3)
        result = pixmap_to_numpy(pixmap)
        assert result.shape == (10, 20, 3)
        assert result.dtype == np.uint8

    def test_rgba_pixmap_to_rgb_array(self) -> None:
        """RGBA pixmap (n=4) is converted to (H, W, 3) by dropping alpha."""
        pixmap = _make_mock_pixmap(width=10, height=5, n=4)
        rgb_pixmap = _make_mock_pixmap(width=10, height=5, n=3)
        with patch("noteeditor.stages.parser.fitz.Pixmap", return_value=rgb_pixmap):
            result = pixmap_to_numpy(pixmap)
        assert result.shape == (5, 10, 3)
        assert result.dtype == np.uint8

    def test_grayscale_pixmap_to_rgb_array(self) -> None:
        """Grayscale pixmap (n=1) is converted to (H, W, 3)."""
        pixmap = _make_mock_pixmap(width=4, height=3, n=1)
        result = pixmap_to_numpy(pixmap)
        assert result.shape == (3, 4, 3)
        assert result.dtype == np.uint8

    def test_returns_copy_not_view(self) -> None:
        """Returned array is writable (independent of pixmap buffer)."""
        pixmap = _make_mock_pixmap(width=2, height=2, n=3)
        result = pixmap_to_numpy(pixmap)
        result[0, 0, 0] = 255
        assert result[0, 0, 0] == 255


class TestRenderPage:
    """Tests for render_page."""

    def test_returns_page_image_with_correct_fields(self) -> None:
        """render_page returns a PageImage with correct metadata."""
        pixmap = _make_mock_pixmap(width=3300, height=2550, n=3)
        page = _make_mock_page(pixmap=pixmap)

        result = render_page(page, page_number=0, dpi=300)

        assert isinstance(result, PageImage)
        assert result.page_number == 0
        assert result.width_px == 3300
        assert result.height_px == 2550
        assert result.dpi == 300
        assert result.image.shape == (2550, 3300, 3)
        assert result.embedded_images == ()

    def test_dpi_affects_resolution(self) -> None:
        """Different DPI values produce correct pixel dimensions from pixmap."""
        pix_150 = _make_mock_pixmap(width=1650, height=1275, n=3)
        page = _make_mock_page()
        page.get_pixmap.return_value = pix_150
        result_150 = render_page(page, 0, 150)
        assert result_150.width_px == 1650
        assert result_150.height_px == 1275

        pix_300 = _make_mock_pixmap(width=3300, height=2550, n=3)
        page.get_pixmap.return_value = pix_300
        result_300 = render_page(page, 0, 300)
        assert result_300.width_px == 3300
        assert result_300.height_px == 2550

    def test_aspect_ratio_calculation(self) -> None:
        """Aspect ratio is width_px / height_px."""
        pixmap = _make_mock_pixmap(width=4000, height=2250, n=3)
        page = _make_mock_page(pixmap=pixmap)

        result = render_page(page, 0, 300)
        expected_ratio = 4000 / 2250
        assert abs(result.aspect_ratio - expected_ratio) < 0.001

    def test_page_number_preserved(self) -> None:
        """Page number from parameter is preserved in result."""
        pixmap = _make_mock_pixmap(width=612, height=792, n=3)
        page = _make_mock_page(pixmap=pixmap)

        result = render_page(page, page_number=5, dpi=72)
        assert result.page_number == 5


class TestParsePdf:
    """Tests for parse_pdf integration."""

    def test_single_page_pdf(self, tmp_path: Path) -> None:
        """Single-page PDF produces one PageImage."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")

        mock_doc = MagicMock()
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(
            return_value=_make_mock_page(pixmap=_make_mock_pixmap())
        )

        with patch("noteeditor.stages.parser.fitz.open", return_value=mock_doc):
            result = parse_pdf(pdf_path, 300)

        assert len(result) == 1
        assert result[0].page_number == 0

    def test_multi_page_pdf(self, tmp_path: Path) -> None:
        """Multi-page PDF produces correct PageImage count."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")

        mock_doc = MagicMock()
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_doc.__getitem__.side_effect = lambda i: _make_mock_page(
            pixmap=_make_mock_pixmap()
        )

        with patch("noteeditor.stages.parser.fitz.open", return_value=mock_doc):
            result = parse_pdf(pdf_path, 300)

        assert len(result) == 5
        for i, page_image in enumerate(result):
            assert page_image.page_number == i

    def test_invalid_pdf_raises_input_error(self) -> None:
        """Non-existent or corrupted PDF raises InputError."""
        with patch(
            "noteeditor.stages.parser.fitz.open", side_effect=Exception("bad pdf")
        ), pytest.raises(InputError, match="Failed to open PDF"):
            parse_pdf(Path("/nonexistent/bad.pdf"), 300)

    def test_zero_dpi_raises_input_error(self) -> None:
        """DPI of zero raises InputError."""
        with pytest.raises(InputError, match="DPI must be a positive integer"):
            parse_pdf(Path("dummy.pdf"), 0)

    def test_negative_dpi_raises_input_error(self) -> None:
        """Negative DPI raises InputError."""
        with pytest.raises(InputError, match="DPI must be a positive integer"):
            parse_pdf(Path("dummy.pdf"), -150)

    def test_single_page_failure_skipped(self, tmp_path: Path) -> None:
        """If one page fails to render, it is skipped and others are returned."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")

        page_ok = _make_mock_page(pixmap=_make_mock_pixmap())
        page_fail = _make_mock_page()
        page_fail.get_pixmap.side_effect = Exception("render error")

        def get_item(idx: int) -> MagicMock:
            if idx == 1:
                return page_fail
            return page_ok

        mock_doc = MagicMock()
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.__len__ = MagicMock(return_value=3)
        mock_doc.__getitem__.side_effect = get_item

        with patch("noteeditor.stages.parser.fitz.open", return_value=mock_doc):
            result = parse_pdf(pdf_path, 300)

        assert len(result) == 2
        assert result[0].page_number == 0
        assert result[1].page_number == 2

    def test_empty_pdf_returns_empty_tuple(self, tmp_path: Path) -> None:
        """PDF with zero pages returns empty tuple."""
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")

        mock_doc = MagicMock()
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_doc.__len__ = MagicMock(return_value=0)

        with patch("noteeditor.stages.parser.fitz.open", return_value=mock_doc):
            result = parse_pdf(pdf_path, 300)

        assert result == ()


class TestExtractEmbeddedResources:
    """Tests for _extract_embedded_resources."""

    def _make_mock_rect(
        self,
        x0: float = 0,
        y0: float = 0,
        x1: float = 100,
        y1: float = 100,
    ) -> MagicMock:
        rect = MagicMock()
        rect.x0 = x0
        rect.y0 = y0
        rect.x1 = x1
        rect.y1 = y1
        return rect

    def _make_mock_image_data(self, w: int = 50, h: int = 50) -> dict:
        """Create mock image data dict like PyMuPDF's extract_image()."""
        import io

        from PIL import Image as PILImage

        img = PILImage.new("RGB", (w, h), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {"image": buf.getvalue(), "ext": "png"}

    def test_no_images_returns_empty(self) -> None:
        """Page with no embedded images returns empty tuple."""
        page = MagicMock()
        page.get_images.return_value = []
        doc = MagicMock()

        result = _extract_embedded_resources(page, doc, 300)
        assert result == ()

    def test_extracts_single_image(self) -> None:
        """Single embedded image is extracted correctly."""
        rect = self._make_mock_rect(10, 20, 200, 170)
        page = MagicMock()
        page.get_images.return_value = [(1, 0, 0, 0, 8, "DeviceRGB", "", "Im0")]
        page.get_image_rects.return_value = [rect]

        doc = MagicMock()
        doc.extract_image.return_value = self._make_mock_image_data(50, 50)

        result = _extract_embedded_resources(page, doc, 300)

        assert len(result) == 1
        assert result[0].index == 1
        assert result[0].width_px == 50
        assert result[0].height_px == 50

    def test_bbox_scaled_by_dpi(self) -> None:
        """Bounding box coordinates are scaled from PDF points to pixels."""
        rect = self._make_mock_rect(72, 72, 144, 144)  # 1x1 inch in PDF points
        page = MagicMock()
        page.get_images.return_value = [(1, 0, 0, 0, 8, "DeviceRGB", "", "Im0")]
        page.get_image_rects.return_value = [rect]

        doc = MagicMock()
        doc.extract_image.return_value = self._make_mock_image_data(50, 50)

        result = _extract_embedded_resources(page, doc, 300)

        assert len(result) == 1
        scale = 300 / 72.0
        assert result[0].bbox.x == pytest.approx(72 * scale)
        assert result[0].bbox.y == pytest.approx(72 * scale)
        assert result[0].bbox.width == pytest.approx(72 * scale)
        assert result[0].bbox.height == pytest.approx(72 * scale)

    def test_deduplicates_same_xref(self) -> None:
        """Same xref appearing multiple times is deduplicated."""
        page = MagicMock()
        page.get_images.return_value = [
            (1, 0, 0, 0, 8, "DeviceRGB", "", "Im0"),
            (1, 0, 0, 0, 8, "DeviceRGB", "", "Im0"),
        ]
        page.get_image_rects.return_value = [self._make_mock_rect()]

        doc = MagicMock()
        doc.extract_image.return_value = self._make_mock_image_data()

        result = _extract_embedded_resources(page, doc, 300)
        assert len(result) == 1

    def test_filters_tiny_images(self) -> None:
        """Images smaller than minimum area are filtered out."""
        rect = self._make_mock_rect(0, 0, 5, 5)  # 5x5 = 25px² at scale=1
        page = MagicMock()
        page.get_images.return_value = [(1, 0, 0, 0, 8, "DeviceRGB", "", "Im0")]
        page.get_image_rects.return_value = [rect]

        doc = MagicMock()

        # At 72 DPI, scale=1, so bbox is 5x5=25 px² which is < 100
        result = _extract_embedded_resources(page, doc, 72)
        assert len(result) == 0

    def test_skips_xref_with_no_rects(self) -> None:
        """Images with no bounding rects are skipped."""
        page = MagicMock()
        page.get_images.return_value = [(1, 0, 0, 0, 8, "DeviceRGB", "", "Im0")]
        page.get_image_rects.return_value = []

        doc = MagicMock()

        result = _extract_embedded_resources(page, doc, 300)
        assert len(result) == 0

    def test_skips_unreadable_image(self) -> None:
        """Images that fail to decode are skipped gracefully."""
        rect = self._make_mock_rect()
        page = MagicMock()
        page.get_images.return_value = [(1, 0, 0, 0, 8, "DeviceRGB", "", "Im0")]
        page.get_image_rects.return_value = [rect]

        doc = MagicMock()
        doc.extract_image.return_value = {"image": b"not_an_image", "ext": "png"}

        result = _extract_embedded_resources(page, doc, 300)
        assert len(result) == 0

    def test_skips_extract_image_failure(self) -> None:
        """Images where extract_image() raises are skipped."""
        rect = self._make_mock_rect()
        page = MagicMock()
        page.get_images.return_value = [(1, 0, 0, 0, 8, "DeviceRGB", "", "Im0")]
        page.get_image_rects.return_value = [rect]

        doc = MagicMock()
        doc.extract_image.side_effect = Exception("corrupt")

        result = _extract_embedded_resources(page, doc, 300)
        assert len(result) == 0

    def test_render_page_passes_embedded_images(self) -> None:
        """render_page includes embedded images when doc is provided."""
        pixmap = _make_mock_pixmap(width=3300, height=2550, n=3)
        page = _make_mock_page(pixmap=pixmap)
        page.get_images.return_value = []
        doc = MagicMock()

        result = render_page(page, 0, 300, doc=doc)

        assert result.embedded_images == ()

    def test_render_page_without_doc_no_embedded(self) -> None:
        """render_page without doc has empty embedded_images."""
        pixmap = _make_mock_pixmap(width=3300, height=2550, n=3)
        page = _make_mock_page(pixmap=pixmap)

        result = render_page(page, 0, 300)

        assert result.embedded_images == ()
