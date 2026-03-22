"""CLI entry point for NoteEditor."""

import click


@click.command()
@click.argument("input_pdf", type=click.Path(exists=True))
@click.option("-o", "--output", default=None, help="Output PPTX file path.")
@click.option("--dpi", default=300, help="Rendering DPI (default: 300).")
def main(input_pdf: str, output: str | None, dpi: int) -> None:
    """Convert a NotebookLM PDF to PPTX."""
    pass
