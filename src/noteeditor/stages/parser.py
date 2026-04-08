"""PDF parsing stage - renders pages and extracts resources."""

from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

from noteeditor.errors import InputError
from noteeditor.models.page import BoundingBox, EmbeddedResource, PageImage

logger = logging.getLogger(__name__)

# Minimum area in px² and extreme aspect ratio thresholds for filtering
_MIN_IMAGE_AREA = 100.0
_MAX_ASPECT_RATIO = 50.0
_MIN_ASPECT_RATIO = 0.02


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


def _extract_embedded_resources(
    page: fitz.Page,
    doc: fitz.Document,
    dpi: int,
) -> tuple[EmbeddedResource, ...]:
    """Extract embedded image resources from a PDF page.

    Filters out tiny decorative elements and extreme aspect ratios.
    Deduplicates by xref (keeps first occurrence).

    Args:
        page: PyMuPDF Page object.
        doc: Parent Document for extracting image data.
        dpi: Rendering DPI for coordinate conversion.

    Returns:
        Tuple of EmbeddedResource objects.
    """
    scale = dpi / 72.0
    seen_xrefs: set[int] = set()
    results: list[EmbeddedResource] = []

    image_list = page.get_images(full=True)

    for img_info in image_list:
        xref = img_info[0]

        # Deduplicate: same xref may appear multiple times
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        try:
            rects = page.get_image_rects(xref)
        except Exception:
            logger.debug("Could not get rects for xref %d, skipping", xref)
            continue

        if not rects:
            continue

        rect = rects[0]  # Use first rect

        # Convert PDF points to pixel coordinates
        bbox = BoundingBox(
            x=rect.x0 * scale,
            y=rect.y0 * scale,
            width=(rect.x1 - rect.x0) * scale,
            height=(rect.y1 - rect.y0) * scale,
        )

        # Filter: skip tiny decorative elements
        area = bbox.width * bbox.height
        if area < _MIN_IMAGE_AREA:
            continue

        # Filter: skip extreme aspect ratios (decorative lines, etc.)
        if bbox.height > 0:
            ratio = bbox.width / bbox.height
        else:
            continue
        if ratio > _MAX_ASPECT_RATIO or ratio < _MIN_ASPECT_RATIO:
            continue

        try:
            img_data = doc.extract_image(xref)
        except Exception:
            logger.debug("Could not extract image xref %d, skipping", xref)
            continue

        if img_data is None or "image" not in img_data:
            continue

        try:
            import io

            from PIL import Image

            pil_img = Image.open(io.BytesIO(img_data["image"]))
            img_array = np.array(pil_img)
            if img_array.ndim == 2:
                img_array = np.stack([img_array] * 3, axis=-1)
            elif img_array.shape[2] == 4:
                img_array = img_array[:, :, :3]
        except Exception:
            logger.debug("Could not decode image xref %d, skipping", xref)
            continue

        h_px, w_px = img_array.shape[:2]

        results.append(
            EmbeddedResource(
                index=xref,
                bbox=bbox,
                image=img_array.copy(),
                width_px=w_px,
                height_px=h_px,
            ),
        )

    return tuple(results)


def render_page(
    page: fitz.Page,
    page_number: int,
    dpi: int,
    doc: fitz.Document | None = None,
) -> PageImage:
    """Render a single PDF page into a PageImage.

    Args:
        page: PyMuPDF Page object.
        page_number: 0-based page index.
        dpi: Rendering resolution in dots per inch.
        doc: Parent Document for extracting embedded resources.

    Returns:
        A frozen PageImage with rendered pixel data and embedded images.
    """
    pixmap = page.get_pixmap(dpi=dpi)
    image = pixmap_to_numpy(pixmap)
    width_px, height_px = pixmap.width, pixmap.height
    aspect_ratio = width_px / height_px if height_px > 0 else 1.0

    embedded_images: tuple[EmbeddedResource, ...] = ()
    if doc is not None:
        try:
            embedded_images = _extract_embedded_resources(page, doc, dpi)
        except Exception:
            logger.debug(
                "Failed to extract embedded resources from page %d",
                page_number,
                exc_info=True,
            )

    return PageImage(
        page_number=page_number,
        width_px=width_px,
        height_px=height_px,
        dpi=dpi,
        aspect_ratio=aspect_ratio,
        image=image,
        embedded_images=embedded_images,
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
                page_image = render_page(page, page_num, dpi, doc=doc)
                results.append(page_image)
            except Exception as e:
                logger.warning(
                    "Failed to render page %d/%d: %s", page_num + 1, total_pages, e
                )

    return tuple(results)
