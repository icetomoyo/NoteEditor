"""Tests for pipeline.py - Pipeline orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from noteeditor.errors import InputError
from noteeditor.infra.config import PipelineConfig
from noteeditor.models.page import PageImage
from noteeditor.pipeline import PipelineResult, run_pipeline


def _make_config(
    input_path: str = "test.pdf",
    output_path: str = "output.pptx",
    dpi: int = 300,
    verbose: bool = False,
    mode: str = "visual",
) -> PipelineConfig:
    """Create a test PipelineConfig (defaulting to visual mode)."""
    return PipelineConfig(
        input_path=Path(input_path),
        output_path=Path(output_path),
        dpi=dpi,
        verbose=verbose,
        mode=mode,  # type: ignore[arg-type]
    )


def _make_page_image(page_number: int = 0) -> PageImage:
    """Create a minimal PageImage for testing."""
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    return PageImage(
        page_number=page_number,
        width_px=100,
        height_px=100,
        dpi=300,
        aspect_ratio=1.0,
        image=image,
    )



class TestPipelineResult:
    """Tests for PipelineResult dataclass."""

    def test_create_result(self) -> None:
        """PipelineResult can be instantiated."""
        result = PipelineResult(
            output_path=Path("output.pptx"),
            total_pages=5,
            success_pages=5,
            failed_pages=0,
        )
        assert result.total_pages == 5
        assert result.success_pages == 5
        assert result.failed_pages == 0

    def test_result_is_frozen(self) -> None:
        """PipelineResult is immutable."""
        result = PipelineResult(
            output_path=Path("output.pptx"),
            total_pages=5,
            success_pages=5,
            failed_pages=0,
        )
        with pytest.raises(AttributeError):
            result.total_pages = 10  # type: ignore[misc]

    def test_result_all_failed(self) -> None:
        """PipelineResult handles all-pages-failed scenario."""
        result = PipelineResult(
            output_path=Path("output.pptx"),
            total_pages=3,
            success_pages=0,
            failed_pages=3,
        )
        assert result.success_pages + result.failed_pages == result.total_pages


class TestRunPipeline:
    """Tests for run_pipeline."""

    def test_single_page_success(self, tmp_path: Path) -> None:
        """Single page PDF produces a PPTX with 1 slide."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        page = _make_page_image(page_number=0)
        with patch("noteeditor.pipeline.parse_pdf", return_value=(page,)):
            result = run_pipeline(config)

        assert isinstance(result, PipelineResult)
        assert result.total_pages == 1
        assert result.success_pages == 1
        assert result.failed_pages == 0
        assert result.output_path == output_path
        assert output_path.exists()

    def test_multi_page_success(self, tmp_path: Path) -> None:
        """Multi-page PDF produces a PPTX with correct slide count."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        pages = (_make_page_image(0), _make_page_image(1), _make_page_image(2))
        with patch("noteeditor.pipeline.parse_pdf", return_value=pages):
            result = run_pipeline(config)

        assert result.total_pages == 3
        assert result.success_pages == 3
        assert result.failed_pages == 0

        from pptx import Presentation

        prs = Presentation(str(output_path))
        assert len(prs.slides) == 3

    def test_parser_error_propagates(self, tmp_path: Path) -> None:
        """InputError from parser is propagated to caller."""
        pdf_path = tmp_path / "bad.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        with (
            patch(
                "noteeditor.pipeline.parse_pdf",
                side_effect=InputError("Failed to open PDF"),
            ),
            pytest.raises(InputError, match="Failed to open PDF"),
        ):
            run_pipeline(config)

    def test_empty_pdf_creates_empty_pptx(self, tmp_path: Path) -> None:
        """Empty PDF (0 pages) creates an empty PPTX."""
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        with patch("noteeditor.pipeline.parse_pdf", return_value=()):
            result = run_pipeline(config)

        assert result.total_pages == 0
        assert result.success_pages == 0
        assert result.failed_pages == 0
        assert output_path.exists()

    def test_partial_failure_counts(self, tmp_path: Path) -> None:
        """Parser returning fewer pages than expected counts as success."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        # Parser returns 2 pages (1 may have failed during parsing)
        pages = (_make_page_image(0), _make_page_image(2))
        with patch("noteeditor.pipeline.parse_pdf", return_value=pages):
            result = run_pipeline(config)

        # All returned pages should be built successfully
        assert result.success_pages == 2
        assert result.total_pages == 2

    def test_builder_error_propagates(self, tmp_path: Path) -> None:
        """Non-InputError from builder is propagated."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        pages = (_make_page_image(0),)
        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=pages),
            patch(
                "noteeditor.pipeline.build_pptx",
                side_effect=RuntimeError("PPTX write failed"),
            ),
            pytest.raises(RuntimeError, match="PPTX write failed"),
        ):
            run_pipeline(config)

    def test_output_parent_dir_created(self, tmp_path: Path) -> None:
        """Pipeline creates output parent directories."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "deep" / "nested" / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path))

        page = _make_page_image(0)
        with patch("noteeditor.pipeline.parse_pdf", return_value=(page,)):
            run_pipeline(config)

        assert output_path.exists()
