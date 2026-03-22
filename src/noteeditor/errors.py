"""Custom exception classes for NoteEditor."""

from __future__ import annotations


class InputError(Exception):
    """Raised when input validation fails (file not found, wrong format, etc.)."""


class OutputError(Exception):
    """Raised when output path is invalid or cannot be written to."""
