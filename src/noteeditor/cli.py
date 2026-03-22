"""CLI entry point for NoteEditor."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from noteeditor.errors import InputError, OutputError

_MIN_DPI = 72
_MAX_DPI = 1200
_DEFAULT_DPI = 300


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
    if dpi < _MIN_DPI or dpi > _MAX_DPI:
        raise InputError(f"DPI must be between {_MIN_DPI} and {_MAX_DPI}, got {dpi}")
    return dpi


def ensure_output_dir(output_path: Path) -> None:
    """Create the parent directory of the output path if it doesn't exist."""
    parent = output_path.parent
    if parent and not parent.exists():
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OutputError(f"Cannot create output directory: {parent}") from e


@click.command()
@click.argument("input_pdf", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output PPTX file path.")
@click.option("--dpi", default=_DEFAULT_DPI, help=f"Rendering DPI (default: {_DEFAULT_DPI}).")
def main(input_pdf: str, output: str | None, dpi: int) -> None:
    """Convert a NotebookLM PDF to PPTX."""
    try:
        pdf_path = validate_pdf(Path(input_pdf))
        validate_dpi(dpi)
        out_path = resolve_output_path(pdf_path, output)
        ensure_output_dir(out_path)

        click.echo(f"Input:  {pdf_path}")
        click.echo(f"Output: {out_path}")
        click.echo(f"DPI:    {dpi}")
        click.echo("Conversion not yet implemented.")

    except InputError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except OutputError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
