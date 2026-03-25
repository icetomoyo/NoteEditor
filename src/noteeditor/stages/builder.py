"""Builder stage - PPTX assembly with python-pptx."""

from __future__ import annotations

import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image
from pptx import Presentation
from pptx.util import Emu

from noteeditor.models.page import PageImage

logger = logging.getLogger(__name__)

# Standard aspect ratio → slide dimensions in inches
# (width, height)
_STANDARD_RATIOS: list[tuple[float, float, float]] = [
    (16 / 9, 13.333, 7.5),
    (4 / 3, 10.0, 7.5),
    (16 / 10, 10.0, 6.25),
]

_EMU_PER_INCH = 914400


def detect_slide_dimensions(aspect_ratio: float) -> tuple[int, int]:
    """Map a page aspect ratio to PPTX slide dimensions in EMU.

    Finds the closest standard ratio (by absolute difference) and
    returns the corresponding slide dimensions.

    Args:
        aspect_ratio: Page width / height (e.g., 1.778 for 16:9).

    Returns:
        Tuple of (width_emu, height_emu).
    """
    best_diff = float("inf")
    best_width_in = 10.0
    best_height_in = 7.5

    for ratio, width_in, height_in in _STANDARD_RATIOS:
        diff = abs(aspect_ratio - ratio)
        if diff < best_diff:
            best_diff = diff
            best_width_in = width_in
            best_height_in = height_in

    return int(best_width_in * _EMU_PER_INCH), int(best_height_in * _EMU_PER_INCH)


def _image_to_bytes(image: np.ndarray) -> bytes:
    """Convert an RGB numpy array to PNG bytes."""
    pil_image = Image.fromarray(image)
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


def build_pptx(
    pages: tuple[PageImage, ...],
    output_path: Path,
) -> Path:
    """Build a PPTX file from page images (screenshot mode).

    Each page's rendered image is added as a full-slide background picture.
    Slide dimensions are determined by the first page's aspect ratio.

    Args:
        pages: Tuple of PageImage objects to include as slides.
        output_path: Where to write the .pptx file.

    Returns:
        The output_path (for chaining).
    """
    # Determine slide dimensions from first page
    if pages:
        width_emu, height_emu = detect_slide_dimensions(pages[0].aspect_ratio)
    else:
        # Default to 16:9 for empty presentations
        width_emu, height_emu = detect_slide_dimensions(16 / 9)

    prs = Presentation()
    prs.slide_width = Emu(width_emu)
    prs.slide_height = Emu(height_emu)

    blank_layout = prs.slide_layouts[6]  # Blank layout

    for page in pages:
        slide = prs.slides.add_slide(blank_layout)
        image_bytes = _image_to_bytes(page.image)
        slide.shapes.add_picture(
            io.BytesIO(image_bytes),
            Emu(0),
            Emu(0),
            Emu(width_emu),
            Emu(height_emu),
        )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_path))

    logger.info("Built PPTX: %s (%d slides)", output_path, len(pages))
    return output_path
