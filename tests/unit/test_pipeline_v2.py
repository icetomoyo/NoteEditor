"""Tests for pipeline v0.3.0 - 9-stage dispatch (Feature 016)."""

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


def _make_background_image() -> np.ndarray:
    """Create a synthetic background image."""
    return np.ones((100, 100, 3), dtype=np.uint8) * 200


def _make_mock_slide(page_image: PageImage) -> MagicMock:
    """Create a mock SlideContent."""
    return MagicMock(
        page_number=page_image.page_number,
        background_image=_make_background_image(),
        full_page_image=page_image.image,
        text_blocks=(),
        image_blocks=(),
        status="success",
    )


def _setup_model_manager() -> tuple[MagicMock, MagicMock]:
    """Create and return (MockMgr class, mock_mgr instance)."""
    mock_mgr = MagicMock()
    mock_mgr.get_layout_model.return_value = MagicMock()
    mock_mgr.get_ocr_model.return_value = MagicMock()
    MockMgr = MagicMock(return_value=mock_mgr)
    return MockMgr, mock_mgr


# ---------------------------------------------------------------------------
# PipelineConfig tests
# ---------------------------------------------------------------------------


class TestPipelineConfigV2:
    """Tests for PipelineConfig with mode and models_dir fields."""

    def test_default_mode_is_editable(self) -> None:
        """Default mode is 'editable' for v0.3.0."""
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
# Pipeline editable mode tests (6-stage)
# ---------------------------------------------------------------------------


class TestRunPipelineEditable:
    """Tests for run_pipeline in editable mode (9-stage)."""

    def test_editable_single_page(self, tmp_path: Path) -> None:
        """Editable mode runs 7 stages for a single page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        bg = _make_background_image()
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background", return_value=bg,
            ) as mock_bg,
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            mock_assemble.return_value = _make_mock_slide(page)
            result = run_pipeline(config)

        assert result.total_pages == 1
        assert result.success_pages == 1
        assert result.failed_pages == 0
        assert result.output_path == output_path
        mock_bg.assert_called_once()

    def test_editable_calls_detect_layout(self, tmp_path: Path) -> None:
        """Editable mode calls detect_layout for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch(
                "noteeditor.pipeline.detect_layout",
                return_value=layout,
            ) as mock_layout,
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
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
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()) as mock_ocr,
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            run_pipeline(config)

        mock_ocr.assert_called_once()

    def test_editable_calls_extract_background(self, tmp_path: Path) -> None:
        """Editable mode calls extract_background for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ) as mock_bg,
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            run_pipeline(config)

        mock_bg.assert_called_once_with(page, layout)

    def test_editable_passes_background_to_assemble(self, tmp_path: Path) -> None:
        """Background image is passed to assemble_slide."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        bg = _make_background_image()
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.extract_background", return_value=bg),
            patch(
                "noteeditor.pipeline.assemble_slide",
            ) as mock_assemble,
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            run_pipeline(config)

        # assemble_slide should receive background_image and image_results
        call_args = mock_assemble.call_args
        assert call_args[0][0] is page
        assert call_args[0][1] is layout
        assert call_args[0][3] is bg  # background_image

    def test_editable_calls_extract_images(self, tmp_path: Path) -> None:
        """Editable mode calls extract_images for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()) as mock_img,
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            run_pipeline(config)

        mock_img.assert_called_once_with(page, layout)

    def test_editable_passes_image_results_to_assemble(self, tmp_path: Path) -> None:
        """Image results are passed to assemble_slide."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            mock_assemble.return_value = _make_mock_slide(page)
            run_pipeline(config)

        # image_results is the 5th positional arg (index 4)
        call_args = mock_assemble.call_args
        assert call_args[0][4] == ()  # image_results

    def test_editable_calls_match_fonts(self, tmp_path: Path) -> None:
        """Editable mode calls match_fonts for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()) as mock_font,
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            run_pipeline(config)

        mock_font.assert_called_once_with(layout, config.fonts_dir)

    def test_editable_passes_font_matches_to_assemble(self, tmp_path: Path) -> None:
        """Font matches are passed to assemble_slide."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            mock_assemble.return_value = _make_mock_slide(page)
            run_pipeline(config)

        # font_matches is the 6th positional arg (index 5)
        call_args = mock_assemble.call_args
        assert call_args[0][5] == ()  # font_matches

    def test_editable_calls_estimate_styles(self, tmp_path: Path) -> None:
        """Editable mode calls estimate_styles for each page."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()) as mock_style,
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            run_pipeline(config)

        mock_style.assert_called_once_with(page, layout)

    def test_editable_passes_style_results_to_assemble(self, tmp_path: Path) -> None:
        """Style results are passed to assemble_slide."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            mock_assemble.return_value = _make_mock_slide(page)
            run_pipeline(config)

        # style_results is the 7th positional arg (index 6)
        call_args = mock_assemble.call_args
        assert call_args[0][6] == ()  # style_results

    def test_editable_fallback_on_layout_error(self, tmp_path: Path) -> None:
        """If layout detection fails, page falls back to screenshot mode."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch(
                "noteeditor.pipeline.detect_layout",
                side_effect=RuntimeError("model error"),
            ),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            result = run_pipeline(config)

        assert result.failed_pages == 1
        assert result.success_pages == 0
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
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch(
                "noteeditor.pipeline.extract_text",
                side_effect=RuntimeError("ocr error"),
            ),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            result = run_pipeline(config)

        assert result.failed_pages == 1
        slides_arg = mock_build.call_args[0][0]
        assert slides_arg[0].status == "fallback"

    def test_editable_fallback_on_background_error(self, tmp_path: Path) -> None:
        """If background extraction fails, page falls back."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="editable")

        page = _make_page_image(0)
        layout = _make_layout_result(0)
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                side_effect=RuntimeError("bg error"),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
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

        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page0, page1)),
            patch(
                "noteeditor.pipeline.detect_layout",
                side_effect=_detect_layout_side_effect,
            ),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide") as mock_assemble,
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
            mock_assemble.return_value = _make_mock_slide(page0)
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
            patch(
                "noteeditor.pipeline.build_pptx", return_value=output_path,
            ) as mock_build,
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

    def test_visual_does_not_call_background(self, tmp_path: Path) -> None:
        """Visual mode does not call extract_background."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.extract_background") as mock_bg,
        ):
            run_pipeline(config)

        mock_bg.assert_not_called()

    def test_visual_does_not_call_extract_images(self, tmp_path: Path) -> None:
        """Visual mode does not call extract_images."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.extract_images") as mock_img,
        ):
            run_pipeline(config)

        mock_img.assert_not_called()

    def test_visual_does_not_call_match_fonts(self, tmp_path: Path) -> None:
        """Visual mode does not call match_fonts."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.match_fonts") as mock_font,
        ):
            run_pipeline(config)

        mock_font.assert_not_called()

    def test_visual_does_not_call_estimate_styles(self, tmp_path: Path) -> None:
        """Visual mode does not call estimate_styles."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 mock")
        output_path = tmp_path / "output.pptx"
        config = _make_config(str(pdf_path), str(output_path), mode="visual")

        page = _make_page_image(0)

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.build_pptx", return_value=output_path),
            patch("noteeditor.pipeline.estimate_styles") as mock_style,
        ):
            run_pipeline(config)

        mock_style.assert_not_called()

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
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=(page,)),
            patch("noteeditor.pipeline.detect_layout", return_value=layout),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
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
        MockMgr, _ = _setup_model_manager()

        with (
            patch("noteeditor.pipeline.parse_pdf", return_value=pages),
            patch(
                "noteeditor.pipeline.detect_layout",
                side_effect=RuntimeError("fail"),
            ),
            patch("noteeditor.pipeline.extract_text", return_value=()),
            patch("noteeditor.pipeline.extract_images", return_value=()),
            patch("noteeditor.pipeline.match_fonts", return_value=()),
            patch("noteeditor.pipeline.estimate_styles", return_value=()),
            patch(
                "noteeditor.pipeline.extract_background",
                return_value=_make_background_image(),
            ),
            patch("noteeditor.pipeline.assemble_slide"),
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ) as mock_build,
            patch("noteeditor.pipeline.ModelManager", MockMgr),
        ):
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
            patch(
                "noteeditor.pipeline.build_editable_pptx",
                return_value=output_path,
            ),
        ):
            result = run_pipeline(config)

        assert result.total_pages == 0
        assert result.success_pages == 0
        assert result.failed_pages == 0
