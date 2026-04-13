"""Tests for infra/progress.py - Progress tracking."""

from __future__ import annotations

from unittest.mock import patch

from noteeditor.infra.progress import STAGE_NAMES, ProgressTracker


class TestProgressTracker:
    """Tests for ProgressTracker."""

    def test_create_tracker(self) -> None:
        tracker = ProgressTracker(total_pages=10)
        assert tracker._total == 10

    def test_non_tty_start_logs(self) -> None:
        """Non-TTY start logs total pages."""
        tracker = ProgressTracker(total_pages=5, verbose=False)
        tracker._is_tty = False
        # Should not raise
        tracker.start()

    def test_non_tty_begin_page(self) -> None:
        tracker = ProgressTracker(total_pages=3)
        tracker._is_tty = False
        tracker.start()
        tracker.begin_page(0)  # Should not raise

    def test_non_tty_begin_stage(self) -> None:
        tracker = ProgressTracker(total_pages=3, verbose=True)
        tracker._is_tty = False
        tracker.start()
        tracker.begin_stage("layout")

    def test_non_tty_end_page(self) -> None:
        tracker = ProgressTracker(total_pages=3)
        tracker._is_tty = False
        tracker.start()
        tracker.begin_page(0)
        tracker.end_page(0, success=True)

    def test_non_tty_end_page_failure(self) -> None:
        tracker = ProgressTracker(total_pages=3)
        tracker._is_tty = False
        tracker.start()
        tracker.begin_page(0)
        tracker.end_page(0, success=False)

    def test_non_tty_finish(self) -> None:
        tracker = ProgressTracker(total_pages=1)
        tracker._is_tty = False
        tracker.start()
        tracker.begin_page(0)
        tracker.end_page(0)
        tracker.finish()

    def test_full_lifecycle(self) -> None:
        """Full non-TTY lifecycle without errors."""
        tracker = ProgressTracker(total_pages=2, verbose=True)
        tracker._is_tty = False
        tracker.start()

        tracker.begin_page(0)
        tracker.begin_stage("layout")
        tracker.begin_stage("ocr")
        tracker.end_page(0, success=True)

        tracker.begin_page(1)
        tracker.begin_stage("layout")
        tracker.end_page(1, success=False)

        tracker.finish()

    def test_tty_with_rich_installed(self) -> None:
        """TTY mode initializes Rich progress (if installed)."""
        tracker = ProgressTracker(total_pages=3)
        tracker._is_tty = True

        try:
            tracker.start()
            tracker.begin_page(0)
            tracker.begin_stage("layout")
            tracker.end_page(0)
            tracker.finish()
        except ImportError:
            pass  # Rich not installed — acceptable in test env


class TestStageNames:
    """Tests for STAGE_NAMES constant."""

    def test_all_stages_have_names(self) -> None:
        expected = {
            "parse", "layout", "ocr", "image",
            "font", "style", "background", "assemble", "build",
        }
        assert set(STAGE_NAMES.keys()) == expected

    def test_names_are_strings(self) -> None:
        for name in STAGE_NAMES.values():
            assert isinstance(name, str)
            assert len(name) > 0
