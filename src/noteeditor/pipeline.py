"""Pipeline orchestrator - serial dispatch of Parser → Builder."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from noteeditor.infra.config import PipelineConfig
from noteeditor.stages.builder import build_pptx
from noteeditor.stages.parser import parse_pdf

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    """Immutable result of a pipeline run."""

    output_path: Path
    total_pages: int
    success_pages: int
    failed_pages: int


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run the full v0.1.0 pipeline: parse PDF → build PPTX.

    Args:
        config: Pipeline configuration (input, output, DPI, etc.).

    Returns:
        PipelineResult with statistics and output path.

    Raises:
        InputError: If the PDF cannot be opened or is invalid.
    """
    # Stage 1: Parse PDF → PageImages
    pages = parse_pdf(config.input_path, config.dpi)

    total = len(pages)

    # Stage 2: Build PPTX from page images
    build_pptx(pages, config.output_path)

    return PipelineResult(
        output_path=config.output_path,
        total_pages=total,
        success_pages=total,
        failed_pages=0,
    )
