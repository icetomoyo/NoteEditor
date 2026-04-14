"""Tests for infra/checkpoint.py - Checkpoint manager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from noteeditor.infra.checkpoint import (
    CheckpointData,
    CheckpointManager,
    _mark_completed,
)


class TestCheckpointData:
    def test_frozen(self) -> None:
        data = CheckpointData(input_pdf="test.pdf", total_pages=5)
        with pytest.raises(AttributeError):
            data.total_pages = 10  # type: ignore[misc]

    def test_is_page_done_empty(self) -> None:
        data = CheckpointData(input_pdf="test.pdf", total_pages=5)
        assert data.is_page_done(0) is False

    def test_is_page_done_true(self) -> None:
        data = CheckpointData(
            input_pdf="test.pdf", total_pages=5,
            completed_pages=((0, "success"), (1, "failed")),
        )
        assert data.is_page_done(0) is True
        assert data.is_page_done(1) is True
        assert data.is_page_done(2) is False

    def test_get_done_pages(self) -> None:
        data = CheckpointData(
            input_pdf="test.pdf", total_pages=5,
            completed_pages=((0, "success"), (3, "failed")),
        )
        assert data.get_done_pages() == frozenset({0, 3})

    def test_get_done_pages_empty(self) -> None:
        data = CheckpointData(input_pdf="test.pdf", total_pages=5)
        assert data.get_done_pages() == frozenset()


class TestMarkCompleted:
    def test_adds_page(self) -> None:
        data = CheckpointData(input_pdf="test.pdf", total_pages=3)
        updated = _mark_completed(data, 0, "success")
        assert updated.is_page_done(0) is True
        assert not data.is_page_done(0)  # original unchanged

    def test_adds_failure_reason(self) -> None:
        data = CheckpointData(input_pdf="test.pdf", total_pages=3)
        updated = _mark_completed(data, 1, "failed", "OCR timeout")
        assert len(updated.failed_reasons) == 1
        assert updated.failed_reasons[0] == (1, "OCR timeout")

    def test_success_no_reason(self) -> None:
        data = CheckpointData(input_pdf="test.pdf", total_pages=3)
        updated = _mark_completed(data, 0, "success")
        assert len(updated.failed_reasons) == 0


class TestCheckpointManager:
    def test_save_and_load(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / ".noteeditor_checkpoint.json"
        mgr = CheckpointManager(ckpt_path)

        data = CheckpointData(
            input_pdf="test.pdf", total_pages=5,
            completed_pages=((0, "success"), (1, "failed")),
            failed_reasons=((1, "layout error"),),
        )
        mgr.save(data)

        loaded = mgr.load("test.pdf")
        assert loaded is not None
        assert loaded.total_pages == 5
        assert loaded.is_page_done(0)
        assert loaded.is_page_done(1)
        assert not loaded.is_page_done(2)

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        mgr = CheckpointManager(tmp_path / "missing.json")
        assert mgr.load("test.pdf") is None

    def test_load_wrong_pdf(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "ckpt.json"
        mgr = CheckpointManager(ckpt_path)

        data = CheckpointData(input_pdf="other.pdf", total_pages=3)
        mgr.save(data)

        assert mgr.load("test.pdf") is None

    def test_load_corrupt_json(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "ckpt.json"
        ckpt_path.write_text("not valid json{{{", encoding="utf-8")
        mgr = CheckpointManager(ckpt_path)
        assert mgr.load("test.pdf") is None

    def test_clear(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "ckpt.json"
        mgr = CheckpointManager(ckpt_path)

        data = CheckpointData(input_pdf="test.pdf", total_pages=3)
        mgr.save(data)
        assert ckpt_path.exists()

        mgr.clear()
        assert not ckpt_path.exists()

    def test_clear_nonexistent(self, tmp_path: Path) -> None:
        mgr = CheckpointManager(tmp_path / "missing.json")
        mgr.clear()  # Should not raise

    def test_save_creates_parent_dir(self, tmp_path: Path) -> None:
        ckpt_path = tmp_path / "nested" / "dir" / "ckpt.json"
        mgr = CheckpointManager(ckpt_path)
        data = CheckpointData(input_pdf="test.pdf", total_pages=1)
        mgr.save(data)
        assert ckpt_path.exists()
