"""sauce.apps.gtk — patch GTK settings.ini for dark/light mode.

Replaces the Python script sauce-gtk-settings-apply.
"""

import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

from ..config import PALETTES_DIR, _detect_mode, load_palette, parse_palette_spec, resolve_variant

_INI_FILES = [
    Path.home() / ".config" / "gtk-3.0" / "settings.ini",
    Path.home() / ".config" / "gtk-4.0" / "settings.ini",
]


def apply(spec: str) -> bool:
    """Patch GTK settings.ini to match the palette's dark/light mode."""
    name, hint = parse_palette_spec(spec)
    palette_path = PALETTES_DIR / f"{name}.json"

    if not palette_path.exists():
        return True  # silently skip

    try:
        palette = load_palette(name)
    except Exception:
        return True

    variant = resolve_variant(palette, hint)
    vdata   = palette.get(variant, {})
    mode    = vdata.get("_mode") or palette.get("_mode") or _detect_mode(vdata.get("bg", "#000000"))
    dark    = mode == "dark"

    gtk_theme = "adw-gtk3-dark" if dark else "adw-gtk3"
    dark_pref = "1" if dark else "0"

    for ini_path in _INI_FILES:
        if not ini_path.exists():
            continue
        cfg = ConfigParser()
        cfg.optionxform = str  # preserve case
        cfg.read(ini_path)

        if not cfg.has_section("Settings"):
            cfg.add_section("Settings")

        cfg.set("Settings", "gtk-theme-name", gtk_theme)
        cfg.set("Settings", "gtk-application-prefer-dark-theme", dark_pref)

        with open(ini_path, "w") as f:
            cfg.write(f, space_around_delimiters=False)

    # Set GNOME / XDG color-scheme preference so libadwaita apps follow the theme
    color_scheme = "prefer-dark" if dark else "prefer-light"
    try:
        subprocess.run(
            ["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", color_scheme],
            timeout=5, capture_output=True,
        )
    except Exception:
        pass  # gsettings not available (non-GNOME setups)

    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sauce-gtk-settings-apply <palette[:variant]>", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if apply(sys.argv[1]) else 1)
