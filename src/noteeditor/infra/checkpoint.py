"""Checkpoint manager - page-level resume support.

Persists processing state to a JSON file so interrupted runs can
be resumed without re-processing already completed pages.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CheckpointData:
    """Immutable snapshot of pipeline processing state."""

    input_pdf: str
    total_pages: int
    completed_pages: tuple[tuple[int, str], ...] = ()  # (page_number, "success"|"failed")
    failed_reasons: tuple[tuple[int, str], ...] = ()  # (page_number, reason)

    def is_page_done(self, page_number: int) -> bool:
        """Check if a page has been processed (success or failed)."""
        return any(p == page_number for p, _ in self.completed_pages)

    def get_done_pages(self) -> frozenset[int]:
        """Return set of all completed page numbers."""
        return frozenset(p for p, _ in self.completed_pages)


def _mark_completed(
    data: CheckpointData,
    page: int,
    status: str,
    reason: str = "",
) -> CheckpointData:
    """Return a new CheckpointData with the page marked as completed."""
    new_completed = data.completed_pages + ((page, status),)
    new_reasons = data.failed_reasons
    if reason:
        new_reasons = data.failed_reasons + ((page, reason),)
    return CheckpointData(
        input_pdf=data.input_pdf,
        total_pages=data.total_pages,
        completed_pages=new_completed,
        failed_reasons=new_reasons,
    )


class CheckpointManager:
    """Load, save, and manage page-level checkpoint files."""

    def __init__(self, checkpoint_path: Path) -> None:
        self._path = checkpoint_path

    @property
    def path(self) -> Path:
        return self._path

    def load(self, expected_pdf: str) -> CheckpointData | None:
        """Load checkpoint if it exists and matches the input PDF.

        Returns None if file doesn't exist, is corrupt, or doesn't
        match the expected PDF path.
        """
        if not self._path.exists():
            return None

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Checkpoint file corrupt, ignoring: %s", exc)
            return None

        if not isinstance(raw, dict):
            return None

        if raw.get("input_pdf") != expected_pdf:
            logger.info(
                "Checkpoint is for a different PDF (%s), ignoring",
                raw.get("input_pdf"),
            )
            return None

        completed = tuple(
            (int(k), v) for k, v in raw.get("completed_pages", {}).items()
        )
        failed = tuple(
            (int(k), v) for k, v in raw.get("failed_reasons", {}).items()
        )

        return CheckpointData(
            input_pdf=raw["input_pdf"],
            total_pages=raw.get("total_pages", 0),
            completed_pages=completed,
            failed_reasons=failed,
        )

    def save(self, data: CheckpointData) -> None:
        """Persist checkpoint to JSON file."""
        payload = {
            "input_pdf": data.input_pdf,
            "total_pages": data.total_pages,
            "completed_pages": {str(p): s for p, s in data.completed_pages},
            "failed_reasons": {str(p): r for p, r in data.failed_reasons},
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def clear(self) -> None:
        """Delete the checkpoint file after successful completion."""
        if self._path.exists():
            self._path.unlink()
            logger.debug("Checkpoint file removed: %s", self._path)
