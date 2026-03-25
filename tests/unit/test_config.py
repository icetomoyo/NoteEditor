"""Tests for infra/config.py - PipelineConfig and build_config()."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from noteeditor.errors import InputError
from noteeditor.infra.config import (
    DEFAULT_DPI,
    MAX_DPI,
    MIN_DPI,
    PipelineConfig,
    build_config,
)


class TestPipelineConfig:
    """Tests for PipelineConfig dataclass."""

    def test_create_config(self) -> None:
        """PipelineConfig can be instantiated with required fields."""
        config = PipelineConfig(
            input_path=Path("test.pdf"),
            output_path=Path("output.pptx"),
        )
        assert config.input_path == Path("test.pdf")
        assert config.output_path == Path("output.pptx")
        assert config.dpi == 300
        assert config.verbose is False

    def test_config_is_frozen(self) -> None:
        """PipelineConfig is immutable."""
        config = PipelineConfig(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
        )
        with pytest.raises(AttributeError):
            config.dpi = 200  # type: ignore[misc]

    def test_config_defaults(self) -> None:
        """PipelineConfig has correct default values."""
        config = PipelineConfig(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
        )
        assert config.dpi == 300
        assert config.verbose is False

    def test_config_custom_values(self) -> None:
        """PipelineConfig accepts custom values."""
        config = PipelineConfig(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
            dpi=150,
            verbose=True,
        )
        assert config.dpi == 150
        assert config.verbose is True


class TestBuildConfig:
    """Tests for build_config() factory function."""

    def test_build_config_defaults(self) -> None:
        """No dpi, no env var → uses default 300."""
        config = build_config(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
        )
        assert config.dpi == DEFAULT_DPI

    def test_build_config_cli_dpi(self) -> None:
        """Explicit CLI dpi is used directly."""
        config = build_config(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
            dpi=150,
        )
        assert config.dpi == 150

    def test_build_config_env_dpi(self) -> None:
        """NOTEEDITOR_DPI env var is used when no CLI dpi."""
        with patch.dict(os.environ, {"NOTEEDITOR_DPI": "200"}):
            config = build_config(
                input_path=Path("in.pdf"),
                output_path=Path("out.pptx"),
            )
        assert config.dpi == 200

    def test_build_config_cli_overrides_env(self) -> None:
        """CLI dpi takes priority over env var."""
        with patch.dict(os.environ, {"NOTEEDITOR_DPI": "200"}):
            config = build_config(
                input_path=Path("in.pdf"),
                output_path=Path("out.pptx"),
                dpi=150,
            )
        assert config.dpi == 150

    def test_build_config_invalid_env_dpi(self) -> None:
        """Invalid NOTEEDITOR_DPI value raises InputError."""
        with (
            patch.dict(os.environ, {"NOTEEDITOR_DPI": "abc"}),
            pytest.raises(InputError, match="invalid DPI"),
        ):
            build_config(
                input_path=Path("in.pdf"),
                output_path=Path("out.pptx"),
            )

    def test_build_config_env_dpi_out_of_range(self) -> None:
        """NOTEEDITOR_DPI out of range raises InputError."""
        with (
            patch.dict(os.environ, {"NOTEEDITOR_DPI": "10"}),
            pytest.raises(InputError, match="DPI must be between"),
        ):
            build_config(
                input_path=Path("in.pdf"),
                output_path=Path("out.pptx"),
            )

    def test_build_config_verbose(self) -> None:
        """Verbose flag is passed through."""
        config = build_config(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
            verbose=True,
        )
        assert config.verbose is True

    def test_build_config_returns_frozen(self) -> None:
        """build_config returns a frozen PipelineConfig."""
        config = build_config(
            input_path=Path("in.pdf"),
            output_path=Path("out.pptx"),
        )
        with pytest.raises(AttributeError):
            config.dpi = 100  # type: ignore[misc]


class TestDpiConstants:
    """Tests for DPI validation constants."""

    def test_constants_exist(self) -> None:
        """DPI constants are exported."""
        assert MIN_DPI == 72
        assert MAX_DPI == 1200
        assert DEFAULT_DPI == 300
