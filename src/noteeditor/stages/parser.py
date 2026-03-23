"""PDF parsing stage - renders pages and extracts resources."""

from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

from noteeditor.errors import InputError
from noteeditor.models.page import PageImage

logger = logging.getLogger(__name__)


def pixmap_to_numpy(pixmap: fitz.Pixmap) -> np.ndarray:
    """Convert a PyMuPDF Pixmap to an RGB numpy array.

    Handles RGB (n=3), RGBA (n=4), and grayscale (n=1) pixmaps by
    always producing a (H, W, 3) uint8 array. Returns a copy that
    is independent of the underlying pixmap buffer.
    """
    if pixmap.n == 4:
        # RGBA → RGB: convert colorspace and extract
        rgb = fitz.Pixmap(fitz.csRGB, pixmap)
        arr = np.frombuffer(rgb.samples, dtype=np.uint8).reshape(rgb.h, rgb.w, 3)
        return arr.copy()
    if pixmap.n == 1:
        # Grayscale → RGB: stack 3 times
        gray = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.h, pixmap.w
        ).copy()
        return np.stack([gray, gray, gray], axis=-1)
    # RGB (n=3)
    arr = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.h, pixmap.w, pixmap.n
    )
    return arr.copy()


def render_page(page: fitz.Page, page_number: int, dpi: int) -> PageImage:
    """Render a single PDF page into a PageImage.

    Args:
        page: PyMuPDF Page object.
        page_number: 0-based page index.
        dpi: Rendering resolution in dots per inch.

    Returns:
        A frozen PageImage with rendered pixel data.
    """
    pixmap = page.get_pixmap(dpi=dpi)
    image = pixmap_to_numpy(pixmap)
    width_px, height_px = pixmap.width, pixmap.height
    aspect_ratio = width_px / height_px if height_px > 0 else 1.0

    return PageImage(
        page_number=page_number,
        width_px=width_px,
        height_px=height_px,
        dpi=dpi,
        aspect_ratio=aspect_ratio,
        image=image,
    )


def parse_pdf(input_path: Path, dpi: int) -> tuple[PageImage, ...]:
    """Parse a PDF file and render each page as a PageImage.

    Args:
        input_path: Path to the PDF file.
        dpi: Rendering resolution in dots per inch (must be positive).

    Returns:
        Tuple of PageImage objects, one per successfully rendered page.
        Failed pages are skipped with a warning.

    Raises:
        InputError: If the PDF cannot be opened or DPI is invalid.
    """
    if dpi <= 0:
        raise InputError(f"DPI must be a positive integer, got {dpi}")

    try:
        doc = fitz.open(str(input_path))
    except Exception as e:
        raise InputError(f"Failed to open PDF: {input_path}") from e

    with doc:
        total_pages = len(doc)
        if total_pages == 0:
            return ()

        results: list[PageImage] = []
        for page_num in range(total_pages):
            try:
                page = doc[page_num]
                page_image = render_page(page, page_num, dpi)
                results.append(page_image)
            except Exception as e:
                logger.warning(
                    "Failed to render page %d/%d: %s", page_num + 1, total_pages, e
                )

    return tuple(results)
