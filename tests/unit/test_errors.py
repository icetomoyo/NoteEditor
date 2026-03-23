"""Tests for noteeditor.errors module."""

from __future__ import annotations

import pytest

from noteeditor.errors import InputError, OutputError


class TestInputError:
    def test_create_input_error(self) -> None:
        err = InputError("file not found: test.pdf")
        assert str(err) == "file not found: test.pdf"

    def test_input_error_is_exception(self) -> None:
        with pytest.raises(InputError):
            raise InputError("bad input")

    def test_input_error_can_be_caught_as_exception(self) -> None:
        try:
            raise InputError("bad input")
        except Exception:
            pass  # Expected: InputError is a subclass of Exception


class TestOutputError:
    def test_create_output_error(self) -> None:
        err = OutputError("cannot write to: /readonly/output.pptx")
        assert str(err) == "cannot write to: /readonly/output.pptx"

    def test_output_error_is_exception(self) -> None:
        with pytest.raises(OutputError):
            raise OutputError("bad output")
