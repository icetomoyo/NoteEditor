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
@click.option(
    "-d",
    "--device",
    type=click.Choice(["auto", "transformers", "ollama", "vllm", "api", "cpu", "gpu"]),
    default="auto",
    help="OCR backend: auto, transformers, ollama, vllm, api, cpu, gpu (default: auto).",
)
@click.option(
    "--retry-pages", default=None,
    help="Only process these page numbers (comma-separated, 0-based). E.g. --retry-pages 3,7",
)
@click.option("--force", is_flag=True, default=False, help="Ignore existing checkpoint.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose output.")
def main(
    input_pdf: str, output: str | None, dpi: int,
    mode: str, device: str, retry_pages: str | None,
    force: bool, verbose: bool,
) -> None:
    """Convert a NotebookLM PDF to PPTX."""
    try:
        pdf_path = validate_pdf(Path(input_pdf))
        validated_dpi = validate_dpi(dpi)
        out_path = resolve_output_path(pdf_path, output)

        parsed_retry: frozenset[int] | None = None
        if retry_pages is not None:
            try:
                parsed_retry = frozenset(int(p.strip()) for p in retry_pages.split(","))
            except ValueError as exc:
                raise InputError(
                    f"Invalid --retry-pages value: {retry_pages!r}. "
                    "Expected comma-separated page numbers (e.g. 3,7,12)."
                ) from exc

        config = build_config(
            input_path=pdf_path,
            output_path=out_path,
            dpi=validated_dpi,
            verbose=verbose,
            mode=mode,  # type: ignore[arg-type]
            device=device,
            retry_pages=parsed_retry,
            force=force,
        )

        click.echo(f"Input:  {pdf_path}")
        click.echo(f"Output: {out_path}")
        click.echo(f"DPI:    {config.dpi}")
        click.echo(f"Mode:   {config.mode}")
        click.echo(f"Device: {config.device}")

        result = run_pipeline(config)

        click.echo(
            f"Done: {result.success_pages}/{result.total_pages} pages → {result.output_path}"
        )

        if result.failed_details:
            click.echo("")
            click.echo(f"Warning: {result.failed_pages} page(s) failed:", err=True)
            for page_num, reason in result.failed_details:
                click.echo(f"  Page {page_num}: {reason}", err=True)
            click.echo("Failed pages use original screenshot as fallback.", err=True)

    except InputError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except OutputError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
