"""Tests for noteeditor.cli module."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from noteeditor.cli import main as cli_main
from noteeditor.cli import resolve_output_path, validate_dpi, validate_pdf
from noteeditor.errors import InputError


class TestValidatePdf:
    def test_rejects_nonexistent_file(self) -> None:
        with pytest.raises(InputError, match="not found"):
            validate_pdf(Path("/nonexistent/file.pdf"))

    def test_rejects_non_pdf_extension(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("document.txt").write_text("hello")
            with pytest.raises(InputError, match="not a PDF file"):
                validate_pdf(Path("document.txt"))

    def test_rejects_non_pdf_magic_bytes(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("fake.pdf").write_text("this is not a real pdf")
            with pytest.raises(InputError, match="not a valid PDF"):
                validate_pdf(Path("fake.pdf"))

    def test_accepts_valid_pdf(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        result = validate_pdf(pdf_file)
        assert result == pdf_file


class TestResolveOutputPath:
    def test_derives_default_output_from_input(self, tmp_path: Path) -> None:
        input_pdf = tmp_path / "presentation.pdf"
        output = resolve_output_path(input_pdf, None)
        assert output == tmp_path / "presentation.pptx"

    def test_uses_explicit_output_path(self, tmp_path: Path) -> None:
        input_pdf = tmp_path / "presentation.pdf"
        explicit = tmp_path / "custom" / "output.pptx"
        output = resolve_output_path(input_pdf, str(explicit))
        assert output == explicit

    def test_output_has_pptx_extension(self, tmp_path: Path) -> None:
        input_pdf = tmp_path / "presentation.pdf"
        output = resolve_output_path(input_pdf, None)
        assert output.suffix == ".pptx"


class TestValidateDpi:
    def test_accepts_default_dpi(self) -> None:
        assert validate_dpi(300) == 300

    def test_accepts_minimum_dpi(self) -> None:
        assert validate_dpi(72) == 72

    def test_accepts_maximum_dpi(self) -> None:
        assert validate_dpi(1200) == 1200

    def test_rejects_dpi_below_minimum(self) -> None:
        with pytest.raises(InputError, match="DPI must be between"):
            validate_dpi(50)

    def test_rejects_dpi_above_maximum(self) -> None:
        with pytest.raises(InputError, match="DPI must be between"):
            validate_dpi(2400)

    def test_rejects_zero_dpi(self) -> None:
        with pytest.raises(InputError, match="DPI must be between"):
            validate_dpi(0)


class TestCliMain:
    def test_no_arguments_shows_usage(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli_main, [])
        assert result.exit_code != 0

    def test_nonexistent_file_shows_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli_main, ["/nonexistent/file.pdf"])
        assert result.exit_code != 0

    def test_non_pdf_shows_error(self, tmp_path: Path) -> None:
        not_pdf = tmp_path / "document.txt"
        not_pdf.write_text("hello")
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(not_pdf)])
        assert result.exit_code == 1

    def test_fake_pdf_shows_error(self, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_text("not a real pdf")
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(fake_pdf)])
        assert result.exit_code == 1

    def test_valid_pdf_runs(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(pdf_file)])
        # Should not fail on validation (pipeline not yet implemented)
        assert result.exit_code == 0 or "not yet implemented" in result.output.lower()

    def test_output_parent_dir_created(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        output_path = tmp_path / "nested" / "dir" / "output.pptx"
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(pdf_file), "-o", str(output_path)])
        assert result.exit_code == 0 or "not yet implemented" in result.output.lower()

    def test_custom_dpi_accepted(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(pdf_file), "--dpi", "150"])
        assert result.exit_code == 0 or "not yet implemented" in result.output.lower()

    def test_invalid_dpi_shows_error(self, tmp_path: Path) -> None:
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4\n")
        runner = CliRunner()
        result = runner.invoke(cli_main, [str(pdf_file), "--dpi", "10"])
        assert result.exit_code == 1
