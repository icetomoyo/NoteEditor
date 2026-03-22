# Feature 001 Test Guide: 项目结构与依赖管理

> Feature ID: 001 | Version: v0.1.0 | Category: Internal | Priority: Critical

## Overview

Verify the project skeleton is correctly set up: package structure, dependencies, data models, and test infrastructure.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed

## Test Cases

### TC-001: Install project with uv

**Steps:**
1. Open terminal in project root
2. Run `uv sync --all-extras`

**Expected:**
- Command completes successfully
- `.venv/` directory is created
- 32 packages installed (numpy, click, rich, pymupdf, python-pptx, pytest, etc.)

---

### TC-002: Import main package

**Steps:**
1. Run `uv run python -c "import noteeditor; print(noteeditor.__version__)"`

**Expected:**
- Output: `0.1.0`
- No import errors

---

### TC-003: Import and instantiate PageImage

**Steps:**
1. Run:
```bash
uv run python -c "
from noteeditor.models.page import PageImage, BoundingBox, EmbeddedResource
import numpy as np
img = np.zeros((100, 200, 3), dtype=np.uint8)
p = PageImage(page_number=0, width_px=200, height_px=100, dpi=300, aspect_ratio=2.0, image=img)
print(f'Page {p.page_number}: {p.width_px}x{p.height_px}')
"
```

**Expected:**
- Output: `Page 0: 200x100`
- No errors

---

### TC-004: Import all stage modules

**Steps:**
1. Run `uv run python -c "import noteeditor.stages.parser, noteeditor.stages.builder; print('OK')"`

**Expected:**
- Output: `OK`
- All stage modules importable

---

### TC-005: Import all data models

**Steps:**
1. Run:
```bash
uv run python -c "
from noteeditor.models import (
    BoundingBox, EmbeddedResource, PageImage,
    RegionLabel, LayoutRegion, LayoutResult,
    OCRResult, ExtractedImage, FontMatch,
    TextBlock, ImageBlock, SlideContent,
)
print(f'{len([BoundingBox, EmbeddedResource, PageImage, RegionLabel, LayoutRegion, LayoutResult, OCRResult, ExtractedImage, FontMatch, TextBlock, ImageBlock, SlideContent])} models imported')
"
```

**Expected:**
- Output: `12 models imported`

---

### TC-006: Run tests

**Steps:**
1. Run `uv run pytest -v`

**Expected:**
- 19 tests collected and passed
- Tests cover: page models, layout models, content models, slide models

---

### TC-007: Verify immutability

**Steps:**
1. Run:
```bash
uv run python -c "
from noteeditor.models.page import PageImage
import numpy as np
p = PageImage(0, 100, 100, 300, 1.0, np.zeros((100,100,3), dtype=np.uint8))
try:
    p.page_number = 1
    print('FAIL: mutation succeeded')
except AttributeError:
    print('PASS: immutable')
"
```

**Expected:**
- Output: `PASS: immutable`

---

### TC-008: Verify project structure

**Steps:**
1. Check the following paths exist:
   - `src/noteeditor/__init__.py`
   - `src/noteeditor/cli.py`
   - `src/noteeditor/pipeline.py`
   - `src/noteeditor/models/page.py`
   - `src/noteeditor/models/layout.py`
   - `src/noteeditor/models/content.py`
   - `src/noteeditor/models/slide.py`
   - `src/noteeditor/stages/parser.py`
   - `src/noteeditor/stages/builder.py`
   - `src/noteeditor/infra/config.py`
   - `tests/unit/test_models.py`
   - `tests/integration/`
   - `tests/fixtures/`
   - `fonts/font_map.yaml`
   - `CLAUDE.md`
   - `pyproject.toml`

**Expected:**
- All paths exist

---

### TC-009: CLI entry point registered

**Steps:**
1. Run `uv run noteeditor --help`

**Expected:**
- Shows usage info with `input-pdf` argument, `-o/--output`, `--dpi` options
- No import errors

---

## Test Summary

| TC | Description | Pass/Fail |
|----|-------------|-----------|
| 001 | uv sync --all-extras | |
| 002 | import noteeditor | |
| 003 | PageImage instantiation | |
| 004 | All stage modules importable | |
| 005 | All 12 data models importable | |
| 006 | 19 tests pass | |
| 007 | Frozen dataclass immutability | |
| 008 | Project file structure | |
| 009 | CLI entry point | |
