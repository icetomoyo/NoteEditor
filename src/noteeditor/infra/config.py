"""Configuration management - PipelineConfig construction."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from noteeditor.errors import InputError

MIN_DPI: int = 72
MAX_DPI: int = 1200
DEFAULT_DPI: int = 300

_ENV_DPI_KEY = "NOTEEDITOR_DPI"
_ENV_DEVICE_KEY = "NOTEEDITOR_DEVICE"
_VALID_DEVICES = ("auto", "transformers", "ollama", "vllm", "api", "cpu", "gpu")

_DEFAULT_MODELS_DIR = Path("~/.noteeditor/models").expanduser()
_DEFAULT_FONTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fonts"


def _resolve_dpi(dpi: int | None) -> int:
    """Resolve DPI from CLI arg, env var, or default.

    Priority: CLI arg > environment variable > default.
    Raises InputError if env var value is invalid.
    """
    if dpi is not None:
        return dpi

    env_val = os.environ.get(_ENV_DPI_KEY)
    if env_val is None:
        return DEFAULT_DPI

    try:
        parsed = int(env_val)
    except ValueError as e:
        raise InputError(
            f"Environment variable {_ENV_DPI_KEY} has invalid DPI value: {env_val!r}"
        ) from e

    if parsed < MIN_DPI or parsed > MAX_DPI:
        raise InputError(
            f"DPI must be between {MIN_DPI} and {MAX_DPI}, got {parsed} "
            f"(from {_ENV_DPI_KEY})"
        )

    return parsed


def _resolve_device(device: str | None) -> str:
    """Resolve device from CLI arg, env var, or default.

    Priority: CLI arg > environment variable > default ("auto").
    Raises InputError if value is invalid.
    """
    if device is not None:
        if device not in _VALID_DEVICES:
            raise InputError(
                f"Invalid device '{device}'. Must be one of: {', '.join(_VALID_DEVICES)}"
            )
        return device

    env_val = os.environ.get(_ENV_DEVICE_KEY)
    if env_val is None:
        return "auto"

    if env_val not in _VALID_DEVICES:
        raise InputError(
            f"Environment variable {_ENV_DEVICE_KEY} has invalid value: {env_val!r}. "
            f"Must be one of: {', '.join(_VALID_DEVICES)}"
        )
    return env_val


def build_config(
    input_path: Path,
    output_path: Path,
    dpi: int | None = None,
    verbose: bool = False,
    mode: Literal["visual", "editable"] = "editable",
    device: str | None = None,
    retry_pages: frozenset[int] | None = None,
    models_dir: Path | None = None,
    fonts_dir: Path | None = None,
) -> PipelineConfig:
    """Build PipelineConfig with CLI > env > defaults priority.

    If dpi is None, falls back to NOTEEDITOR_DPI env var, then default.
    If device is None, falls back to NOTEEDITOR_DEVICE env var, then "auto".
    """
    resolved_dpi = _resolve_dpi(dpi)
    resolved_device = _resolve_device(device)
    return PipelineConfig(
        input_path=input_path,
        output_path=output_path,
        dpi=resolved_dpi,
        verbose=verbose,
        mode=mode,
        device=resolved_device,
        retry_pages=retry_pages,
        models_dir=models_dir if models_dir is not None else _DEFAULT_MODELS_DIR,
        fonts_dir=fonts_dir if fonts_dir is not None else _DEFAULT_FONTS_DIR,
    )


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable pipeline configuration.

    Supports both visual (screenshot) and editable modes.
    """

    input_path: Path
    output_path: Path
    dpi: int = 300
    verbose: bool = False
    mode: Literal["visual", "editable"] = "editable"
    device: str = "auto"
    retry_pages: frozenset[int] | None = None
    models_dir: Path = _DEFAULT_MODELS_DIR
    fonts_dir: Path = _DEFAULT_FONTS_DIR
