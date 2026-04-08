"""CLI entry point for NoteEditor."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from noteeditor.errors import InputError, OutputError
from noteeditor.infra.config import MAX_DPI, MIN_DPI, build_config
from noteeditor.pipeline import run_pipeline


def validate_pdf(input_path: Path) -> Path:
    """Validate that the input file exists and is a valid PDF.

    Checks file extension first, then magic bytes for reliability.
    """
    if not input_path.exists():
        raise InputError(f"Input file not found: {input_path}")

    if input_path.suffix.lower() != ".pdf":
        raise InputError(f"Input file is not a PDF file: {input_path}")

    try:
        header = input_path.read_bytes()[:5]
    except OSError as e:
        raise InputError(f"Cannot read input file: {input_path}") from e

    if header != b"%PDF-":
        raise InputError(f"Input file is not a valid PDF (bad magic bytes): {input_path}")

    return input_path


def resolve_output_path(input_pdf: Path, output: str | None) -> Path:
    """Derive the output PPTX path from the input PDF path.

    If no explicit output is given, uses the same directory and filename
    with a .pptx extension.
    """
    if output is not None:
        return Path(output)
    return input_pdf.with_suffix(".pptx")


def validate_dpi(dpi: int) -> int:
    """Validate that the DPI value is within the acceptable range."""
    if dpi < MIN_DPI or dpi > MAX_DPI:
        raise InputError(f"DPI must be between {MIN_DPI} and {MAX_DPI}, got {dpi}")
    return dpi


@click.command()
@click.argument("input_pdf", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output PPTX file path.")
@click.option("--dpi", default=300, help="Rendering DPI (default: 300).")
@click.option(
    "--mode",
    type=click.Choice(["visual", "editable"]),
    default="editable",
    help="Output mode: visual (screenshot) or editable (default: editable).",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose output.")
def main(input_pdf: str, output: str | None, dpi: int, mode: str, verbose: bool) -> None:
    """Convert a NotebookLM PDF to PPTX."""
    try:
        pdf_path = validate_pdf(Path(input_pdf))
        validated_dpi = validate_dpi(dpi)
        out_path = resolve_output_path(pdf_path, output)

        config = build_config(
            input_path=pdf_path,
            output_path=out_path,
            dpi=validated_dpi,
            verbose=verbose,
            mode=mode,  # type: ignore[arg-type]
        )

        click.echo(f"Input:  {pdf_path}")
        click.echo(f"Output: {out_path}")
        click.echo(f"DPI:    {config.dpi}")
        click.echo(f"Mode:   {config.mode}")

        result = run_pipeline(config)

        click.echo(
            f"Done: {result.success_pages}/{result.total_pages} pages → {result.output_path}"
        )

    except InputError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except OutputError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
