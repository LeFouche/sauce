"""sauce.apps.vscodium — deep-merge generated settings fragment into VSCodium settings.json.

Replaces the bash script sauce-vscodium-apply.
Drops the jq dependency; merges using Python's json module.
"""

import json
import sys
from pathlib import Path

from ..config import (
    PALETTES_DIR, generated_path, load_palette, parse_palette_spec, resolve_variant,
)

_SETTINGS_PATH = Path.home() / ".config" / "VSCodium" / "User" / "settings.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base (like jq '. * $frag[0]')."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def apply(spec: str) -> bool:
    """Deep-merge the VSCodium settings fragment for the given palette spec."""
    name, hint = parse_palette_spec(spec)
    palette_path = PALETTES_DIR / f"{name}.json"

    if not palette_path.exists():
        print(f"Palette not found: {palette_path}", file=sys.stderr)
        return False
    if not _SETTINGS_PATH.exists():
        return True  # VSCodium not installed — silently skip

    try:
        palette = load_palette(name)
    except Exception as e:
        print(f"Cannot load palette: {e}", file=sys.stderr)
        return False

    variant  = resolve_variant(palette, hint)
    fragment_path = generated_path(name, variant, "vscodium/settings-fragment.json")

    if not fragment_path.exists():
        print(
            f"Fragment not found: {fragment_path} — run: sauce generate {name}",
            file=sys.stderr,
        )
        return False

    try:
        settings = json.loads(_SETTINGS_PATH.read_text())
        fragment = json.loads(fragment_path.read_text())
        merged   = _deep_merge(settings, fragment)

        # Atomic write via temp file
        tmp = _SETTINGS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
        tmp.replace(_SETTINGS_PATH)
    except Exception as e:
        print(f"Error applying VSCodium settings: {e}", file=sys.stderr)
        return False

    return True


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: sauce-vscodium-apply <palette[:variant]>", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if apply(sys.argv[1]) else 1)
