# Test Guide: FEATURE 002 - CLI 入口与参数解析

> Version: v0.1.0 | Generated: 2026-03-22

## Overview

Feature 002 implements the CLI entry point with input validation, output path resolution, and DPI configuration.

## Prerequisites

```bash
uv sync --all-extras
uv run pip install -e .
```

## Test Cases

### TC-001: No arguments shows usage

**Steps:**
1. Run `noteeditor` with no arguments
2. Observe the output

**Expected:**
- Exit code != 0
- Usage/help text is displayed

```bash
uv run noteeditor
```

### TC-002: Non-existent input file

**Steps:**
1. Run `noteeditor` with a path that doesn't exist

**Expected:**
- Exit code != 0
- Error message indicates file not found

```bash
uv run noteeditor /nonexistent/file.pdf
```

### TC-003: Non-PDF file extension

**Steps:**
1. Create a non-PDF file: `echo "hello" > test.txt`
2. Run `noteeditor test.txt`

**Expected:**
- Exit code = 1
- Error: "not a PDF file"

```bash
uv run noteeditor test.txt
```

### TC-004: Fake PDF (wrong magic bytes)

**Steps:**
1. Create a file with .pdf extension but invalid content: `echo "not a pdf" > fake.pdf`
2. Run `noteeditor fake.pdf`

**Expected:**
- Exit code = 1
- Error: "not a valid PDF (bad magic bytes)"

```bash
uv run noteeditor fake.pdf
```

### TC-005: Valid PDF with default output

**Steps:**
1. Create a minimal valid PDF: `echo -n "%PDF-1.4" > valid.pdf`
2. Run `noteeditor valid.pdf`

**Expected:**
- Exit code = 0
- Output shows: Input path, Output path (same dir, .pptx extension), DPI = 300

```bash
uv run noteeditor valid.pdf
```

### TC-006: Explicit output path

**Steps:**
1. Create a minimal valid PDF
2. Run `noteeditor valid.pdf -o custom_output.pptx`

**Expected:**
- Exit code = 0
- Output path shows `custom_output.pptx`

```bash
uv run noteeditor valid.pdf -o custom_output.pptx
```

### TC-007: Custom DPI value

**Steps:**
1. Create a minimal valid PDF
2. Run `noteeditor valid.pdf --dpi 150`

**Expected:**
- Exit code = 0
- Output shows DPI = 150

```bash
uv run noteeditor valid.pdf --dpi 150
```

### TC-008: Invalid DPI (too low)

**Steps:**
1. Create a minimal valid PDF
2. Run `noteeditor valid.pdf --dpi 10`

**Expected:**
- Exit code = 1
- Error: "DPI must be between 72 and 1200"

```bash
uv run noteeditor valid.pdf --dpi 10
```

### TC-009: Output parent directory auto-creation

**Steps:**
1. Create a minimal valid PDF
2. Run `noteeditor valid.pdf -o nested/dir/output.pptx` (where `nested/dir/` doesn't exist)

**Expected:**
- Exit code = 0
- Directory `nested/dir/` is created

```bash
uv run noteeditor valid.pdf -o nested/dir/output.pptx
```

## Automated Test Results

- **Tests:** 47 passed, 0 failed
- **Coverage:** 94% statements
- **Lint:** ruff check passed
- **Type check:** mypy passed
