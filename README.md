# NoteEditor

NotebookLM PDF to PPTX converter with pixel-level visual fidelity.

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Or with uv
uv sync --all-extras

# Run
noteeditor input.pdf -o output.pptx
```

## Project Structure

```
src/noteeditor/       # Main source code
  cli.py              # CLI entry point
  pipeline.py         # Pipeline orchestrator
  models/             # Data models (frozen dataclasses)
  stages/             # Pipeline stages (parser, layout, ocr, etc.)
  infra/              # Infrastructure (config, progress, checkpoint)
tests/                # Tests (unit, integration, fixtures)
fonts/                # NotebookLM font files and mapping
docs/                 # Design documents (PRD, HLD, DD)
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=noteeditor

# Lint
uv run ruff check .

# Type check
uv run mypy src/
```

## License

Apache 2.0 - see [LICENSE](LICENSE)
