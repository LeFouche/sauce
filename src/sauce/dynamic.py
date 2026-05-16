"""sauce.dynamic — wallpaper-driven palette generation via matugen."""

import json
import subprocess
import sys
from pathlib import Path

from . import config as _config
from .render import generate_palette
from .switch import switch_palette

_MATUGEN_TO_SAUCE: dict[str, str] = {
    "background":         "bg",
    "surface":            "bg1",
    "surface_variant":    "bg2",
    "on_background":      "fg",
    "on_surface_variant": "fg1",
    "outline":            "subtext",
    "primary":            "blue",
    "secondary":          "teal",
    "tertiary":           "purple",
    "error":              "red",
    "secondary_container": "cyan",
    "tertiary_container":  "green",
    "primary_container":   "orange",
    "on_tertiary":         "yellow",
    "on_primary":          "pink",
}


def parse_matugen_output(json_text: str) -> dict:
    """Parse matugen JSON output → sauce palette dict (without top-level metadata)."""
    data = json.loads(json_text)
    schemes = data["colors"]

    palette: dict = {}
    for scheme_name, scheme in schemes.items():
        variant_data: dict[str, str] = {"_mode": scheme_name}
        for matugen_role, sauce_role in _MATUGEN_TO_SAUCE.items():
            color = scheme.get(matugen_role, "")
            if color and sauce_role not in variant_data:
                variant_data[sauce_role] = color
        palette[scheme_name] = variant_data

    return palette


def run_dynamic(image_path: str, variant: str = "dark") -> bool:
    """
    Generate a dynamic palette from a wallpaper image using matugen.

    Calls matugen, writes palettes/dynamic.json, generates and switches.
    Returns True on success, False on any failure.
    """
    result = subprocess.run(
        ["matugen", "image", "--json", image_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"error: matugen failed:\n{result.stderr}", file=sys.stderr)
        return False

    try:
        palette = parse_matugen_output(result.stdout)
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"error: could not parse matugen output: {exc}", file=sys.stderr)
        return False

    palette["_name"] = "Dynamic"
    palette["_default_variant"] = variant

    out_path = _config.PALETTES_DIR / "dynamic.json"
    out_path.write_text(json.dumps(palette, indent=2, ensure_ascii=False))
    print(f"  Written: {out_path}")

    if not generate_palette("dynamic", force=True):
        return False
    return switch_palette(f"dynamic:{variant}")
