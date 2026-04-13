"""Progress display - CLI progress reporting with rich.

Provides a ProgressTracker that shows page-level and stage-level progress
in TTY environments using Rich, and falls back to plain logging otherwise.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)

# Stage names displayed to the user
STAGE_NAMES: dict[str, str] = {
    "parse": "Parsing PDF",
    "layout": "Layout detection",
    "ocr": "OCR text extraction",
    "image": "Image extraction",
    "font": "Font matching",
    "style": "Style estimation",
    "background": "Background extraction",
    "assemble": "Assembling slide",
    "build": "Building PPTX",
}


class ProgressTracker:
    """Track and display pipeline progress.

    Uses Rich progress bars in TTY environments, falls back to
    plain log messages otherwise.
    """

    def __init__(self, total_pages: int, verbose: bool = False) -> None:
        self._total = total_pages
        self._verbose = verbose
        self._is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        self._progress: Any = None
        self._page_task: Any = None
        self._stage_task: Any = None
        self._start_time = time.monotonic()
        self._page_start_time = 0.0

    def start(self) -> None:
        """Initialize the progress display."""
        if self._is_tty:
            try:
                from rich.progress import (
                    BarColumn,
                    MofNCompleteColumn,
                    Progress,
                    SpinnerColumn,
                    TextColumn,
                    TimeElapsedColumn,
                    TimeRemainingColumn,
                )

                self._progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=None,  # default stderr
                )
                self._page_task = self._progress.add_task(
                    "Pages", total=self._total,
                )
                self._stage_task = self._progress.add_task(
                    "Stage", total=None, visible=False,
                )
                self._progress.start()
            except ImportError:
                self._is_tty = False

        if not self._is_tty:
            logger.info("Processing %d pages...", self._total)

    def begin_page(self, page_number: int) -> None:
        """Signal the start of processing a page."""
        self._page_start_time = time.monotonic()
        if self._is_tty and self._progress is not None:
            self._progress.update(
                self._page_task,
                description=f"Page {page_number + 1}/{self._total}",
            )
        else:
            logger.info("[%d/%d] Processing page %d", page_number + 1, self._total, page_number)

    def begin_stage(self, stage: str) -> None:
        """Signal the start of a processing stage."""
        name = STAGE_NAMES.get(stage, stage)
        if self._is_tty and self._progress is not None:
            self._progress.update(
                self._stage_task,
                description=name,
                visible=True,
            )
        elif self._verbose:
            logger.info("  %s...", name)

    def end_page(self, page_number: int, success: bool = True) -> None:
        """Signal the end of processing a page."""
        if self._is_tty and self._progress is not None:
            self._progress.advance(self._page_task)
            self._progress.update(self._stage_task, visible=False)
        else:
            elapsed = time.monotonic() - self._page_start_time
            status = "ok" if success else "FAILED"
            logger.info(
                "[%d/%d] Page %d %s (%.1fs)",
                page_number + 1, self._total, page_number, status, elapsed,
            )

    def finish(self) -> None:
        """Finalize and close the progress display."""
        if self._is_tty and self._progress is not None:
            self._progress.stop()
        total_elapsed = time.monotonic() - self._start_time
        logger.info("Total processing time: %.1fs", total_elapsed)
