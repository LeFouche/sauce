"""sauce.apps.spicetify — apply spicetify theme if Spotify is running.

Replaces the bash script sauce-spicetify-apply.
"""

import shutil
import subprocess
import sys

from ..config import PALETTES_DIR, load_palette, parse_palette_spec, resolve_variant


def _spotify_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-x", "spotify"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


def apply(spec: str) -> bool:
    """Apply spicetify theme for the given palette spec, if Spotify is running."""
    if not _spotify_running():
        return True
    if not shutil.which("spicetify"):
        return True

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
    community = vdata.get("_spicetify_community") or ""

    if community:
        subprocess.run(
            ["spicetify", "config", "current_theme", community, "color_scheme", "Base"],
            capture_output=True, timeout=10,
        )
    else:
        subprocess.run(
            ["spicetify", "config", "current_theme", "generated", "color_scheme", "Base"],
            capture_output=True, timeout=10,
        )

    # Apply in background — mirrors the original `spicetify apply &`
    subprocess.Popen(["spicetify", "apply"])
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sauce-spicetify-apply <palette[:variant]>", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if apply(sys.argv[1]) else 1)
