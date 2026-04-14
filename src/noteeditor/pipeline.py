"""Pipeline orchestrator - serial dispatch of processing stages."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from noteeditor.infra.checkpoint import CheckpointData, CheckpointManager, _mark_completed
from noteeditor.infra.config import PipelineConfig
from noteeditor.infra.model_manager import ModelManager
from noteeditor.infra.progress import ProgressTracker
from noteeditor.models.page import PageImage
from noteeditor.models.slide import SlideContent
from noteeditor.stages.background import extract_background
from noteeditor.stages.builder import assemble_slide, build_editable_pptx, build_pptx
from noteeditor.stages.font import match_fonts
from noteeditor.stages.image import extract_images
from noteeditor.stages.layout import detect_layout
from noteeditor.stages.ocr import extract_text
from noteeditor.stages.parser import parse_pdf
from noteeditor.stages.style import estimate_styles

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """Immutable result of a pipeline run."""

    output_path: Path
    total_pages: int
    success_pages: int
    failed_pages: int
    failed_details: tuple[tuple[int, str], ...] = ()  # (page_number, reason)


def _make_fallback_slide(
    page: PageImage,
) -> SlideContent:
    """Create a fallback SlideContent for a failed page."""
    return SlideContent(
        page_number=page.page_number,
        background_image=None,
        full_page_image=page.image,
        text_blocks=(),
        image_blocks=(),
        status="fallback",
    )


def _run_editable_pipeline(
    pages: tuple[PageImage, ...],
    config: PipelineConfig,
    progress: ProgressTracker,
    checkpoint_mgr: CheckpointManager | None = None,
    checkpoint_data: CheckpointData | None = None,
) -> tuple[list[SlideContent], list[tuple[int, str]]]:
    """Run the editable pipeline stages.

    Returns (slides, failed_details) where failed_details is a list of
    (page_number, reason) tuples.
    """
    if not pages:
        return [], []

    model_mgr = ModelManager(models_dir=config.models_dir, device=config.device)
    layout_session = model_mgr.get_layout_model()
    ocr_backend = model_mgr.create_ocr_backend()
    lama_session = model_mgr.get_lama_model()

    slides: list[SlideContent] = []
    failures: list[tuple[int, str]] = []

    retry_set = config.retry_pages
    done_pages = checkpoint_data.get_done_pages() if checkpoint_data is not None else frozenset()
    ckpt = checkpoint_data

    for page in pages:
        progress.begin_page(page.page_number)

        # Skip pages already completed in checkpoint (unless retry overrides)
        if page.page_number in done_pages and (
            retry_set is None or page.page_number not in retry_set
        ):
            slides.append(_make_fallback_slide(page))
            progress.end_page(page.page_number, success=True)
            continue

        # Skip pages not in retry set (if retry_pages is specified)
        if retry_set is not None and page.page_number not in retry_set:
            slides.append(_make_fallback_slide(page))
            progress.end_page(page.page_number, success=True)
            continue

        success = True
        try:
            progress.begin_stage("layout")
            layout = detect_layout(page, layout_session)

            progress.begin_stage("ocr")
            ocr_results = extract_text(page, layout, ocr_backend)

            progress.begin_stage("image")
            image_results = extract_images(page, layout)

            progress.begin_stage("font")
            font_matches = match_fonts(layout, config.fonts_dir)

            progress.begin_stage("style")
            style_results = estimate_styles(page, layout, ocr_results)

            progress.begin_stage("background")
            background = extract_background(page, layout, lama_session)

            progress.begin_stage("assemble")
            slide = assemble_slide(
                page, layout, ocr_results, background, image_results,
                font_matches, style_results,
            )
        except Exception as exc:
            logger.warning(
                "Page %d failed, falling back to screenshot",
                page.page_number,
                exc_info=True,
            )
            slide = _make_fallback_slide(page)
            failures.append((page.page_number, str(exc)))
            success = False

        slides.append(slide)
        progress.end_page(page.page_number, success=success)

        # Update checkpoint after each page
        if checkpoint_mgr is not None and ckpt is not None:
            status = "success" if success else "failed"
            reason = failures[-1][1] if not success and failures else ""
            ckpt = _mark_completed(ckpt, page.page_number, status, reason)
            checkpoint_mgr.save(ckpt)

    return slides, failures


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run the full pipeline: parse PDF → build PPTX.

    In 'visual' mode: parse → build screenshot PPTX.
    In 'editable' mode: parse → layout → OCR → image → font → style →
        background → assemble → build editable PPTX.

    Args:
        config: Pipeline configuration (input, output, DPI, mode, device, etc.).

    Returns:
        PipelineResult with statistics and output path.

    Raises:
        InputError: If the PDF cannot be opened or is invalid.
    """
    # Stage 1: Parse PDF → PageImages
    pages = parse_pdf(config.input_path, config.dpi)
    total = len(pages)

    if config.mode == "visual":
        # Visual mode: direct screenshot PPTX
        build_pptx(pages, config.output_path)
        return PipelineResult(
            output_path=config.output_path,
            total_pages=total,
            success_pages=total,
            failed_pages=0,
        )

    # Warn about out-of-range retry pages
    if config.retry_pages is not None:
        valid_page_nums = {p.page_number for p in pages}
        invalid = config.retry_pages - valid_page_nums
        if invalid:
            logger.warning(
                "Retry pages out of range (ignored): %s", sorted(invalid),
            )

    # Checkpoint setup
    checkpoint_path = config.input_path.parent / ".noteeditor_checkpoint.json"
    checkpoint_mgr = CheckpointManager(checkpoint_path)
    checkpoint_data: CheckpointData | None = None

    if not config.force:
        checkpoint_data = checkpoint_mgr.load(str(config.input_path))
        if checkpoint_data is not None:
            done = checkpoint_data.get_done_pages()
            logger.info("Resuming from checkpoint: %d pages already done", len(done))

    if checkpoint_data is None:
        checkpoint_data = CheckpointData(
            input_pdf=str(config.input_path),
            total_pages=total,
        )

    # Editable mode: multi-stage pipeline with progress tracking
    progress = ProgressTracker(total_pages=total, verbose=config.verbose)
    progress.start()

    slides, failures = _run_editable_pipeline(
        pages, config, progress, checkpoint_mgr, checkpoint_data,
    )

    progress.begin_stage("build")
    build_editable_pptx(tuple(slides), config.output_path, config.dpi)

    progress.finish()

    # Clear checkpoint on successful completion
    checkpoint_mgr.clear()

    return PipelineResult(
        output_path=config.output_path,
        total_pages=total,
        success_pages=total - len(failures),
        failed_pages=len(failures),
        failed_details=tuple(failures),
    )
