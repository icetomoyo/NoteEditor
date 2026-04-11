# NoteEditor - Project Instructions

## Project Overview

NoteEditor converts Google NotebookLM PDF presentations into high-fidelity PPTX files using a multi-stage pipeline architecture.

## Development Setup

```bash
uv sync --all-extras
```

## Running Commands

- **Tests**: `uv run pytest`
- **Tests with coverage**: `uv run pytest --cov=noteeditor`
- **Lint**: `uv run ruff check .`
- **Type check**: `uv run mypy src/`
- **Format**: `uv run ruff format .`

## Architecture

Multi-stage pipeline: Parser → Layout(+NMS) → OCR(via Backend) → Image → Font → Style → Background → Assemble → Builder

- Layout detection: PP-DocLayout-V3 via ONNX Runtime
- OCR: GLM-OCR via pluggable backend (Transformers / Ollama / vLLM / API)
- All data between stages uses frozen dataclasses (immutable)
- See `docs/DD.md` for detailed design

## Key Conventions

- **Immutability**: All data models are `@dataclass(frozen=True)`. Never mutate, always create new instances.
- **Small files**: Keep files under 400 lines, extract utilities when larger.
- **Error handling**: Handle errors at every level, never silently swallow exceptions.
- **Input validation**: Validate at system boundaries (CLI input, file I/O, API responses).
- **Type hints**: All public functions must have type hints.

## Design Documents

- `docs/PRD.md` - Product requirements
- `docs/HLD.md` - High-level architecture
- `docs/DD.md` - Detailed data structures and algorithms
- `docs/features/v0.1.0.md` ~ `v0.4.0.md` - Completed version feature specs
- `docs/features/v0.5.0.md` - Final version feature specs

## Version Planning

- v0.1.0: Project skeleton, basic PDF→screenshot→PPTX chain ✅
- v0.2.0: Editable MVP (layout + OCR + text boxes) ✅
- v0.3.0: Background extraction + image extraction ✅
- v0.4.0: Font matching + style estimation ✅
- v0.5.0: Final release (OCR backend refactor, quality fixes, UX, LaMA, checkpoint)

## Commit Message Format

```
<type>: <description>

Types: feat, fix, refactor, docs, test, chore, perf, ci
```
