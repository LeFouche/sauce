"""sauce.switch — Apply a palette: generate, link/copy, reload."""

import shutil
import subprocess
import sys
from pathlib import Path

from .config import (
    PALETTES_DIR, expand_path, generated_path, load_palette, load_registry,
    parse_palette_spec, resolve_variant, set_active,
)
from .render import generate_palette, is_up_to_date


def is_preview(name: str) -> bool:
    return name.startswith("_")


def switch_file(file_entry: dict, generated: Path) -> None:
    """
    Apply one file entry: either copy (for "copy": true) or symlink.
    Skips entries with empty output string.
    """
    output_str = file_entry.get("output", "")
    if not output_str:
        return

    dest = expand_path(output_str)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if file_entry.get("copy"):
        if dest.is_symlink():
            dest.unlink()
        shutil.copy2(generated, dest)
    else:
        # Atomic replace via temp symlink
        tmp = dest.parent / (dest.name + ".tmp")
        try:
            tmp.symlink_to(generated)
            tmp.replace(dest)
        except Exception:
            if dest.exists() or dest.is_symlink():
                dest.unlink()
            dest.symlink_to(generated)


def run_reloads(registry: dict, spec: str) -> None:
    """Run reload commands for all apps, passing full spec ('palette:variant') as $1."""
    for app in registry["app"]:
        cmd_str = app.get("reload_cmd", "")
        if not cmd_str:
            continue
        # Helper scripts (path-like) receive the full spec as $1
        if cmd_str.startswith("~") or cmd_str.startswith("/"):
            cmd = [expand_path(cmd_str).as_posix(), spec]
        else:
            cmd = cmd_str
        try:
            subprocess.run(cmd, shell=isinstance(cmd, str),
                           timeout=10, capture_output=True)
        except Exception as e:
            print(f"  warning: reload '{cmd_str}' failed: {e}", file=sys.stderr)


def switch_palette(spec: str, reload: bool = True) -> bool:
    """
    Full switch: parse spec → resolve variant → generate (if needed)
    → link/copy → set active → reload.
    """
    name, hint = parse_palette_spec(spec)
    palette_path = PALETTES_DIR / f"{name}.json"
    if not palette_path.exists():
        print(f"error: unknown palette '{name}'", file=sys.stderr)
        return False

    try:
        palette  = load_palette(name)
        registry = load_registry()
    except Exception as e:
        print(f"error: cannot load palette/registry: {e}", file=sys.stderr)
        return False

    variant  = resolve_variant(palette, hint)
    full_spec = f"{name}:{variant}"

    # Generate if not up to date
    sentinel_rel = registry["app"][0]["files"][0]["template"]
    sentinel = generated_path(name, variant, sentinel_rel)
    if not is_up_to_date(palette_path, sentinel):
        if not generate_palette(name, variant):
            return False

    # Apply each file entry
    for app in registry["app"]:
        for file_entry in app["files"]:
            tmpl_rel = file_entry["template"]
            gen_path = generated_path(name, variant, tmpl_rel)
            if not gen_path.exists():
                print(f"  warning: generated file missing: {gen_path}", file=sys.stderr)
                continue
            try:
                switch_file(file_entry, gen_path)
            except Exception as e:
                print(f"  warning: applying {tmpl_rel}: {e}", file=sys.stderr)

    # Track active palette (skip for preview palettes)
    if not is_preview(name):
        set_active(full_spec)

    # Reload apps
    if reload:
        run_reloads(registry, full_spec)

    display_name = palette.get("_name", name)
    print(f"Applied: {display_name} ({variant})")

    # Desktop notification (best-effort)
    try:
        subprocess.run(
            ["notify-send", "Theme", f"Switched to {display_name} ({variant})",
             "--icon", "preferences-desktop-theme"],
            timeout=3, capture_output=True
        )
    except Exception:
        pass

    return True
