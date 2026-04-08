"""Tests for pipeline v0.2.0 - 5-stage dispatch (Feature 012)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from noteeditor.infra.config import PipelineConfig, build_config
from noteeditor.models.layout import LayoutResult
from noteeditor.models.page import PageImage
from noteeditor.pipeline import run_pipeline

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    input_path: str = "test.pdf",
    output_path: str = "output.pptx",
    dpi: int = 300,
    verbose: bool = False,
    mode: str = "editable",
) -> PipelineConfig:
    """Create a test PipelineConfig."""
    return PipelineConfig(
        input_path=Path(input_path),
        output_path=Path(output_path),
        dpi=dpi,
        verbose=verbose,
        mode=mode,
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


def _make_layout_result(page_number: int = 0) -> LayoutResult:
    """Create an empty LayoutResult."""
    return LayoutResult(page_number=page_number, regions=())


# ---------------------------------------------------------------------------
# PipelineConfig tests
# ---------------------------------------------------------------------------


class TestPipelineConfigV2:
    """Tests for PipelineConfig with mode and models_dir fields."""

    def test_default_mode_is_editable(self) -> None:
        """Default mode is 'editable' for v0.2.0."""
        config = PipelineConfig(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
        )
        assert config.mode == "editable"

    def test_mode_visual(self) -> None:
        """Mode can be set to 'visual'."""
        config = PipelineConfig(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
            mode="visual",
        )
        assert config.mode == "visual"

    def test_default_models_dir(self) -> None:
        """Default models_dir points to ~/.noteeditor/models."""
        config = PipelineConfig(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
        )
        expected = Path("~/.noteeditor/models").expanduser()
        assert config.models_dir == expected

    def test_custom_models_dir(self) -> None:
        """Custom models_dir is accepted."""
        custom = Path("/tmp/models")
        config = PipelineConfig(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
            models_dir=custom,
        )
        assert config.models_dir == custom

    def test_frozen(self) -> None:
        """PipelineConfig remains immutable."""
        config = PipelineConfig(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
        )
        with pytest.raises(AttributeError):
            config.mode = "visual"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# build_config tests
# ---------------------------------------------------------------------------


class TestBuildConfigV2:
    """Tests for build_config with new fields."""

    def test_build_config_passes_mode(self) -> None:
        """build_config passes mode to PipelineConfig."""
        config = build_config(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
            mode="visual",
        )
        assert config.mode == "visual"

    def test_build_config_default_mode(self) -> None:
        """build_config defaults mode to 'editable'."""
        config = build_config(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
        )
        assert config.mode == "editable"

    def test_build_config_custom_models_dir(self) -> None:
        """build_config passes custom models_dir."""
        config = build_config(
            input_path=Path("a.pdf"),
            output_path=Path("b.pptx"),
            models_dir=Path("/custom/models"),
        )
        assert config.models_dir == Path("/custom/models")


# ---------------------------------------------------------------------------
# Pipeline editable mode tests
# ---------------------------------------------------------------------------


class TestRunPipelineEditable:
    """Tests for run_pipeline in editable mode (5-stage)."""

    def test_editable_single_page(self, tmp_path: Path) -> None:
        """Editable mode runs 5 stages for a single page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch("noteeditor.pipeline.build_editable_pptx", return_value=output_path),
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            mock_assemble.return_value = MagicMock(
                page_number=0,
                background_image=None,
                full_page_image=page.image,
                text_blocks=(),
                image_blocks=(),
                status="success",
            )

            result = run_pipeline(config)

        assert result.total_pages == 1
        assert result.success_pages == 1
        assert result.failed_pages == 0
        assert result.output_path == output_path

    def test_editable_calls_detect_layout(self, tmp_path: Path) -> None:
        """Editable mode calls detect_layout for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout) as mock_layout,
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch(
                "noteeditor.pipeline.assemble_slide",
                return_value=MagicMock(
                    page_number=0,
                    background_image=None,
                    full_page_image=page.image,
                    text_blocks=(),
                    image_blocks=(),
                    status="success",
                ),
            ),
            patch("noteeditor.pipeline.build_editable_pptx", return_value=output_path),
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            run_pipeline(config)

        mock_layout.assert_called_once()

    def test_editable_calls_extract_text(self, tmp_path: Path) -> None:
        """Editable mode calls extract_text for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()) as mock_ocr,
            patch(
                "noteeditor.pipeline.assemble_slide",
                return_value=MagicMock(
                    page_number=0,
                    background_image=None,
                    full_page_image=page.image,
                    text_blocks=(),
                    image_blocks=(),
                    status="success",
                ),
            ),
            patch("noteeditor.pipeline.build_editable_pptx", return_value=output_path),
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            run_pipeline(config)

        mock_ocr.assert_called_once()

    def test_editable_fallback_on_layout_error(self, tmp_path: Path) -> None:
        """If layout detection fails, page falls back to screenshot mode."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", side_effect=RuntimeError("model error")),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            result = run_pipeline(config)

        assert result.failed_pages == 1
        assert result.success_pages == 0
        # build_editable_pptx should still be called with a fallback slide
        mock_build.assert_called_once()
        slides_arg = mock_build.call_args[0][0]
        assert len(slides_arg) == 1
        assert slides_arg[0].status == "fallback"

    def test_editable_fallback_on_ocr_error(self, tmp_path: Path) -> None:
        """If OCR fails, page falls back to screenshot mode."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch(
                "noteeditor.pipeline.extract_text",
                side_effect=RuntimeError("ocr error"),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            result = run_pipeline(config)

        assert result.failed_pages == 1
        slides_arg = mock_build.call_args[0][0]
        assert slides_arg[0].status == "fallback"

    def test_editable_mixed_success_and_failure(self, tmp_path: Path) -> None:
        """Some pages succeed, others fail — correct counts."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page0 = _make_page_image(0)
        page1 = _make_page_image(1)
        layout0 = _make_layout_result(0)

        def _detect_layout_side_effect(page, session):
            if page.page_number == 0:
                return layout0
            raise RuntimeError("layout failed for page 1")

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page0, page1)),
            patch(
                "noteeditor.pipeline.detect_layout",
                side_effect=_detect_layout_side_effect,
            ),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch("noteeditor.pipeline.build_editable_pptx", return_value=output_path),
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            mock_assemble.return_value = MagicMock(
                page_number=0,
                background_image=None,
                full_page_image=page0.image,
                text_blocks=(),
                image_blocks=(),
                status="success",
            )

            result = run_pipeline(config)

        assert result.total_pages == 2
        assert result.success_pages == 1
        assert result.failed_pages == 1


# ---------------------------------------------------------------------------
# Pipeline visual mode tests
# ---------------------------------------------------------------------------


class TestRunPipelineVisual:
    """Tests for run_pipeline in visual mode (2-stage, v0.1.0 behavior)."""

    def test_visual_single_page(self, tmp_path: Path) -> None:
        """Visual mode runs only parse + build (no layout/ocr)."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path) as mock_build,
        ):
            result = run_pipeline(config)

        assert result.total_pages == 1
        assert result.success_pages == 1
        assert result.failed_pages == 0
        mock_build.assert_called_once()

    def test_visual_does_not_call_layout(self, tmp_path: Path) -> None:
        """Visual mode does not call detect_layout."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.detect_layout") as mock_layout,
        ):
            run_pipeline(config)

        mock_layout.assert_not_called()

    def test_visual_does_not_call_ocr(self, tmp_path: Path) -> None:
        """Visual mode does not call extract_text."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.extract_text") as mock_ocr,
        ):
            run_pipeline(config)

        mock_ocr.assert_not_called()

    def test_visual_does_not_create_model_manager(self, tmp_path: Path) -> None:
        """Visual mode does not create ModelManager."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            run_pipeline(config)

        MockMgr.assert_not_called()


# ---------------------------------------------------------------------------
# ModelManager integration
# ---------------------------------------------------------------------------


class TestModelManagerCreation:
    """Tests that ModelManager is created correctly in editable mode."""

    def test_uses_config_models_dir(self, tmp_path: Path) -> None:
        """ModelManager is created with config.models_dir."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        custom_models = tmp_path / "my_models"
        config = PipelineConfig(
            input_path=pdf_path,
            output_path=output_path,
            models_dir=custom_models,
        )

        page = _make_page_image(0)
        layout = _make_layout_result(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch(
                "noteeditor.pipeline.assemble_slide",
                return_value=MagicMock(
                    page_number=0,
                    background_image=None,
                    full_page_image=page.image,
                    text_blocks=(),
                    image_blocks=(),
                    status="success",
                ),
            ),
            patch("noteeditor.pipeline.build_editable_pptx", return_value=output_path),
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            run_pipeline(config)

        MockMgr.assert_called_once_with(models_dir=custom_models)


# ---------------------------------------------------------------------------
# All pages fallback
# ---------------------------------------------------------------------------


class TestAllPagesFallback:
    """Tests when all pages fail in editable mode."""

    def test_all_pages_fallback(self, tmp_path: Path) -> None:
        """All pages fail → all fallback, still produces output."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        pages = (_make_page_image(0), _make_page_image(1))

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=pages),
            patch("noteeditor.pipeline.detect_layout", side_effect=RuntimeError("fail")),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager") as MockMgr,
        ):
            mock_mgr = MagicMock()
            mock_mgr.get_layout_model.return_value = MagicMock()
            mock_mgr.get_ocr_model.return_value = MagicMock()
            MockMgr.return_value = mock_mgr

            result = run_pipeline(config)

        assert result.total_pages == 2
        assert result.success_pages == 0
        assert result.failed_pages == 2
        slides_arg = mock_build.call_args[0][0]
        assert all(s.status == "fallback" for s in slides_arg)

    def test_empty_pages_editable(self, tmp_path: Path) -> None:
        """Empty PDF in editable mode produces empty PPTX."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=()),
            patch("noteeditor.pipeline.build_editable_pptx", return_value=output_path),
        ):
            result = run_pipeline(config)

        assert result.total_pages == 0
        assert result.success_pages == 0
        assert result.failed_pages == 0
