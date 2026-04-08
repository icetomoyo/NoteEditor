"""Font matching stage - NotebookLM font mapping."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from noteeditor.models.content import FontMatch
from noteeditor.models.layout import LayoutResult, RegionLabel

logger = logging.getLogger(__name__)

# Text region labels eligible for font matching.
_TEXT_LABELS: frozenset[RegionLabel] = frozenset(
    {
        RegionLabel.TITLE,
        RegionLabel.BODY_TEXT,
        RegionLabel.EQUATION,
        RegionLabel.CODE_BLOCK,
    }
)

# Default font when no mapping exists.
_DEFAULT_FONT = "Arial"


def _load_font_map(fonts_dir: Path) -> dict[str, dict[str, str]]:
    """Load font_map.yaml from fonts directory.

    Returns empty dict on missing file or parse errors.
    """
    yaml_path = fonts_dir / "font_map.yaml"
    if not yaml_path.is_file():
        logger.debug("font_map.yaml not found in %s", fonts_dir)
        return {}

    try:
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        logger.debug("Failed to parse font_map.yaml")
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def _match_font(
    region_id: str,
    label: RegionLabel,
    font_map: dict[str, dict[str, str]],
    fonts_dir: Path,
) -> FontMatch:
    """Match a font for a single region label."""
    entry = font_map.get(label.value)

    if entry is None:
        return FontMatch(
            region_id=region_id,
            label=label,
            font_name=_DEFAULT_FONT,
            font_path=None,
            system_fallback=_DEFAULT_FONT,
            is_fallback=True,
        )

    font_name = entry.get("font_name", _DEFAULT_FONT)
    font_file = entry.get("font_file")
    system_fallback = entry.get("system_fallback")

    if font_file:
        font_path = fonts_dir / font_file
        if font_path.is_file():
            return FontMatch(
                region_id=region_id,
                label=label,
                font_name=font_name,
                font_path=font_path,
                system_fallback=system_fallback,
                is_fallback=False,
            )

    return FontMatch(
        region_id=region_id,
        label=label,
        font_name=font_name,
        font_path=None,
        system_fallback=system_fallback,
        is_fallback=True,
    )


def match_fonts(
    layout_result: LayoutResult,
    fonts_dir: Path,
) -> tuple[FontMatch, ...]:
    """Match fonts for text regions using font_map.yaml."""
    font_map = _load_font_map(fonts_dir)

    results: list[FontMatch] = []
    for region in layout_result.regions:
        if region.label not in _TEXT_LABELS:
            continue
        results.append(_match_font(region.region_id, region.label, font_map, fonts_dir))

    return tuple(results)
