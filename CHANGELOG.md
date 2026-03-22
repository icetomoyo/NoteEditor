# Changelog

## [Unreleased]

---

## [0.1.1] - 2026-03-22

### Added
- CLI input validation: file existence, PDF extension check, magic bytes verification
- Output path auto-derivation (input_dir/input_stem.pptx)
- DPI validation (72-1200 range, default 300)
- Output parent directory auto-creation
- InputError and OutputError custom exception classes
- 26 new unit tests for CLI (47 total, 94% coverage)

---

## [0.1.0] - 2026-03-22

### Added
- Project skeleton with uv-based dependency management (hatchling build backend)
- Core frozen dataclasses: BoundingBox, PageImage, PageMetadata, EmbeddedResource, LayoutRegion, LayoutResult, OCRResult, ExtractedImage, FontMatch, TextBlock, ImageBlock, SlideContent
- StrEnum-based RegionLabel with 11 region types (title, body_text, image, table, etc.)
- CLI skeleton with click (input_pdf, --output, --dpi options)
- Pipeline orchestrator skeleton with 7 stage modules (parser, layout, ocr, image, background, font, builder)
- Infrastructure modules (config, model_manager, progress, checkpoint)
- NotebookLM font mapping template (Google Sans family)
- 21 unit tests covering all model types with immutability verification
- CLAUDE.md with project conventions and architecture reference
- Comprehensive README with project structure and development instructions

### Dependencies
- pymupdf, python-pptx, pillow, numpy, click, rich, pyyaml, httpx, onnxruntime
- Dev: pytest, pytest-cov, ruff, mypy

---

## [0.0.1] - 2026-03-22

### Added
- Project initialization with Apache 2.0 license
- PRD: NotebookLM PDF to PPTX conversion tool requirements
- HLD: 6-stage pipeline architecture design
- DD: Detailed data structures and stage specifications
- v0.1.0 feature plan (8 features: project skeleton, CLI, PDF rendering, aspect ratio detection, pipeline orchestrator, PPTX output, config management, progress display)

---

<!-- last-sync: 3254f9d -->
