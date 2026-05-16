import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


MATUGEN_JSON = json.dumps({
    "colors": {
        "dark": {
            "primary":            "#89b4fa",
            "on_primary":         "#ffffff",
            "primary_container":  "#1e3a5f",
            "on_primary_container": "#cdd6f4",
            "secondary":          "#94e2d5",
            "on_secondary":       "#ffffff",
            "secondary_container": "#003e3a",
            "on_secondary_container": "#cdd6f4",
            "tertiary":           "#b4befe",
            "on_tertiary":        "#ffffff",
            "tertiary_container": "#2a2a6e",
            "on_tertiary_container": "#cdd6f4",
            "error":              "#f38ba8",
            "on_error":           "#ffffff",
            "error_container":    "#5e1a1a",
            "on_error_container": "#cdd6f4",
            "background":         "#1e1e2e",
            "on_background":      "#cdd6f4",
            "surface":            "#313244",
            "on_surface":         "#cdd6f4",
            "surface_variant":    "#45475a",
            "on_surface_variant": "#6c7086",
            "outline":            "#a6adc8",
            "outline_variant":    "#6c7086",
        },
        "light": {
            "primary":            "#1e66f5",
            "on_primary":         "#ffffff",
            "primary_container":  "#d5e3ff",
            "on_primary_container": "#001b6a",
            "secondary":          "#179299",
            "on_secondary":       "#ffffff",
            "secondary_container": "#b6f0f0",
            "on_secondary_container": "#002020",
            "tertiary":           "#7287fd",
            "on_tertiary":        "#ffffff",
            "tertiary_container": "#dde1ff",
            "on_tertiary_container": "#001060",
            "error":              "#d20f39",
            "on_error":           "#ffffff",
            "error_container":    "#ffd9de",
            "on_error_container": "#400011",
            "background":         "#eff1f5",
            "on_background":      "#4c4f69",
            "surface":            "#e6e9ef",
            "on_surface":         "#4c4f69",
            "surface_variant":    "#ccd0da",
            "on_surface_variant": "#9ca0b0",
            "outline":            "#6c6f85",
            "outline_variant":    "#9ca0b0",
        },
    }
})


def test_parse_matugen_output_maps_classic_roles(data_dir):
    from sauce.dynamic import parse_matugen_output
    palette = parse_matugen_output(MATUGEN_JSON)
    dark = palette["dark"]
    assert dark["bg"]      == "#1e1e2e"   # background → bg
    assert dark["fg"]      == "#cdd6f4"   # on_background → fg
    assert dark["blue"]    == "#89b4fa"   # primary → blue
    assert dark["teal"]    == "#94e2d5"   # secondary → teal
    assert dark["purple"]  == "#b4befe"   # tertiary → purple
    assert dark["red"]     == "#f38ba8"   # error → red
    assert dark["subtext"] == "#a6adc8"   # outline → subtext
    assert dark["_mode"]   == "dark"


def test_parse_matugen_output_has_light_variant(data_dir):
    from sauce.dynamic import parse_matugen_output
    palette = parse_matugen_output(MATUGEN_JSON)
    assert "light" in palette
    assert palette["light"]["bg"] == "#eff1f5"


def test_run_dynamic_writes_palette_json(data_dir):
    from sauce.dynamic import run_dynamic

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = MATUGEN_JSON

    with patch("sauce.dynamic.subprocess.run", return_value=mock_result), \
         patch("sauce.dynamic.generate_palette", return_value=True), \
         patch("sauce.dynamic.switch_palette",   return_value=True):
        result = run_dynamic("/fake/wallpaper.jpg", variant="dark")

    assert result is True
    palette_file = data_dir / "palettes" / "dynamic.json"
    assert palette_file.exists()
    data = json.loads(palette_file.read_text())
    assert data["_name"] == "Dynamic"
    assert data["dark"]["bg"] == "#1e1e2e"


def test_run_dynamic_returns_false_on_matugen_failure(data_dir):
    from sauce.dynamic import run_dynamic

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "matugen: image not found"

    with patch("sauce.dynamic.subprocess.run", return_value=mock_result):
        result = run_dynamic("/nonexistent.jpg")

    assert result is False
