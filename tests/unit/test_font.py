"""Tests for font matching stage."""

from __future__ import annotations

from pathlib import Path

import yaml

from noteeditor.models.content import FontMatch
from noteeditor.models.layout import BoundingBox, LayoutRegion, LayoutResult, RegionLabel
from noteeditor.stages.font import _load_font_map, _match_font, match_fonts

# --- Helpers ---


def _make_region(
    region_id: str = "r0",
    label: RegionLabel = RegionLabel.TITLE,
) -> LayoutRegion:
    return LayoutRegion(
        bbox=BoundingBox(x=0, y=0, width=100, height=50),
        label=label,
        confidence=0.9,
        region_id=region_id,
    )


def _make_layout(regions: tuple[LayoutRegion, ...] = ()) -> LayoutResult:
    return LayoutResult(page_number=0, regions=regions)


def _write_font_map(
    tmp_path: Path,
    data: dict | None = None,
) -> Path:
    """Write a font_map.yaml and return the fonts directory."""
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    if data is None:
        data = {
            "title": {
                "font_name": "Google Sans",
                "font_file": "GoogleSans-Bold.ttf",
                "system_fallback": "Arial",
            },
            "body_text": {
                "font_name": "Google Sans",
                "font_file": "GoogleSans-Regular.ttf",
                "system_fallback": "Arial",
            },
            "code_block": {
                "font_name": "Google Sans Mono",
                "font_file": "GoogleSansMono-Regular.ttf",
                "system_fallback": "Consolas",
            },
        }
    (fonts_dir / "font_map.yaml").write_text(yaml.dump(data))
    return fonts_dir


# --- _load_font_map ---


class TestLoadFontMap:
    def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        result = _load_font_map(fonts_dir)
        assert "title" in result
        assert result["title"]["font_name"] == "Google Sans"

    def test_returns_empty_on_missing_file(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "nofonts"
        fonts_dir.mkdir()
        result = _load_font_map(fonts_dir)
        assert result == {}

    def test_returns_empty_on_invalid_yaml(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        (fonts_dir / "font_map.yaml").write_text("{{invalid yaml")
        result = _load_font_map(fonts_dir)
        assert result == {}


# --- _match_font ---


class TestMatchFont:
    def test_title_with_font_file(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        (fonts_dir / "GoogleSans-Bold.ttf").write_bytes(b"mock font")
        font_map = _load_font_map(fonts_dir)

        result = _match_font("r0", RegionLabel.TITLE, font_map, fonts_dir)

        assert result.region_id == "r0"
        assert result.font_name == "Google Sans"
        assert result.font_path is not None
        assert result.is_fallback is False

    def test_title_without_font_file(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        font_map = _load_font_map(fonts_dir)

        result = _match_font("r0", RegionLabel.TITLE, font_map, fonts_dir)

        assert result.font_name == "Google Sans"
        assert result.font_path is None
        assert result.system_fallback == "Arial"
        assert result.is_fallback is True

    def test_code_block_uses_consolas_fallback(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        font_map = _load_font_map(fonts_dir)

        result = _match_font("r0", RegionLabel.CODE_BLOCK, font_map, fonts_dir)

        assert result.system_fallback == "Consolas"

    def test_unknown_label_uses_arial_default(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        font_map = _load_font_map(fonts_dir)

        result = _match_font("r0", RegionLabel.IMAGE, font_map, fonts_dir)

        assert result.font_name == "Arial"
        assert result.is_fallback is True

    def test_empty_font_map_uses_arial(self, tmp_path: Path) -> None:
        fonts_dir = tmp_path / "fonts"
        fonts_dir.mkdir()
        result = _match_font("r0", RegionLabel.TITLE, {}, fonts_dir)

        assert result.font_name == "Arial"
        assert result.is_fallback is True

    def test_preserves_region_id(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        font_map = _load_font_map(fonts_dir)

        result = _match_font("my_region_42", RegionLabel.TITLE, font_map, fonts_dir)

        assert result.region_id == "my_region_42"

    def test_preserves_label(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        font_map = _load_font_map(fonts_dir)

        result = _match_font("r0", RegionLabel.BODY_TEXT, font_map, fonts_dir)

        assert result.label == RegionLabel.BODY_TEXT


# --- match_fonts (public) ---


class TestMatchFonts:
    def test_returns_font_match_for_text_regions(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        layout = _make_layout((
            _make_region("r0", RegionLabel.TITLE),
            _make_region("r1", RegionLabel.BODY_TEXT),
        ))

        result = match_fonts(layout, fonts_dir)

        assert len(result) == 2
        assert all(isinstance(f, FontMatch) for f in result)

    def test_skips_non_text_regions(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        layout = _make_layout((
            _make_region("r0", RegionLabel.IMAGE),
            _make_region("r1", RegionLabel.TABLE),
            _make_region("r2", RegionLabel.TITLE),
        ))

        result = match_fonts(layout, fonts_dir)

        assert len(result) == 1
        assert result[0].region_id == "r2"

    def test_empty_layout(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        layout = _make_layout()

        result = match_fonts(layout, fonts_dir)

        assert result == ()

    def test_equation_included(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        layout = _make_layout((
            _make_region("r0", RegionLabel.EQUATION),
        ))

        result = match_fonts(layout, fonts_dir)

        assert len(result) == 1
        # Equation has no explicit mapping → falls back to Arial
        assert result[0].is_fallback is True

    def test_mixed_text_and_non_text(self, tmp_path: Path) -> None:
        fonts_dir = _write_font_map(tmp_path)
        layout = _make_layout((
            _make_region("r0", RegionLabel.TITLE),
            _make_region("r1", RegionLabel.IMAGE),
            _make_region("r2", RegionLabel.CODE_BLOCK),
            _make_region("r3", RegionLabel.BODY_TEXT),
        ))

        result = match_fonts(layout, fonts_dir)

        assert len(result) == 3
        ids = [f.region_id for f in result]
        assert ids == ["r0", "r2", "r3"]
