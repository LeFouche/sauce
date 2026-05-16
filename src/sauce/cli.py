"""sauce CLI — theme management tool."""

import sys

from .config import (
    PALETTES_DIR, TEMPLATES_DIR, SAUCE_DIR,
    find_spec_by_qs_name, get_active, list_palettes, load_palette,
    load_registry, palette_variants, parse_palette_spec, resolve_variant,
)
from .render import generate_all, generate_palette
from .switch import switch_palette


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_generate(args: list[str]) -> int:
    force = "--force" in args
    args  = [a for a in args if a != "--force"]

    if "--all" in args:
        return 0 if generate_all(force) else 1
    elif args:
        name, variant = parse_palette_spec(args[0])
        return 0 if generate_palette(name, variant, force) else 1
    else:
        print("Usage: sauce generate [<palette>[:<variant>] | --all] [--force]")
        return 1


def cmd_switch(args: list[str]) -> int:
    reload = "--no-reload" not in args
    args   = [a for a in args if a != "--no-reload"]

    if not args:
        print("Usage: sauce switch <palette>[:<variant>] [--no-reload]")
        return 1
    return 0 if switch_palette(args[0], reload=reload) else 1


def cmd_list(_args: list[str]) -> int:
    palettes = list_palettes()
    active_spec = get_active()
    active_name, active_variant = parse_palette_spec(active_spec) if active_spec else (None, None)

    for p in palettes:
        try:
            pal      = load_palette(p)
            variants = palette_variants(pal)
        except Exception:
            variants = []

        variant_strs = []
        for v in variants:
            if p == active_name and v == active_variant:
                variant_strs.append(f"{v} ←")
            else:
                variant_strs.append(v)

        print(f"  {p:<20} {'  '.join(variant_strs)}")
    return 0


def cmd_current(_args: list[str]) -> int:
    active = get_active()
    if active:
        print(active)
        return 0
    print("(no active palette)", file=sys.stderr)
    return 1


def cmd_validate(_args: list[str]) -> int:
    """Validate all templates render successfully for all palettes × variants."""
    import re
    TOKEN_RE = re.compile(r'\{\{([a-z][a-z0-9_]*)\}\}')

    from .config import build_token_context
    registry = load_registry()
    palettes = list_palettes()
    errors   = 0

    templates: list[str] = []
    seen: set[str] = set()
    for app in registry["app"]:
        for fe in app["files"]:
            rel = fe["template"]
            if rel not in seen:
                seen.add(rel)
                templates.append(rel)

    for pal_name in palettes:
        try:
            pal      = load_palette(pal_name)
            variants = palette_variants(pal)
        except Exception as e:
            print(f"  [FAIL] {pal_name}: cannot load palette: {e}")
            errors += 1
            continue

        for variant in variants:
            try:
                tokens = build_token_context(pal, variant)
            except Exception as e:
                print(f"  [FAIL] {pal_name}:{variant}: cannot build tokens: {e}")
                errors += 1
                continue

            for tmpl_rel in templates:
                tmpl_path = TEMPLATES_DIR / tmpl_rel
                if not tmpl_path.exists():
                    print(f"  [FAIL] {pal_name}:{variant}/{tmpl_rel}: template file missing")
                    errors += 1
                    continue
                text = tmpl_path.read_text()
                for m in TOKEN_RE.finditer(text):
                    key = m.group(1)
                    if key not in tokens:
                        print(f"  [FAIL] {pal_name}:{variant}/{tmpl_rel}: unknown token '{{{{{key}}}}}' ")
                        errors += 1

    total_variants = sum(
        len(palette_variants(load_palette(p))) for p in palettes
        if (PALETTES_DIR / f"{p}.json").exists()
    )
    if errors == 0:
        print(f"OK: {len(palettes)} palettes × {total_variants} variants × {len(templates)} templates — all tokens resolved")
    else:
        print(f"{errors} error(s) found")
    return 0 if errors == 0 else 1


def cmd_doctor(_args: list[str]) -> int:
    """Check the active theme for drift: broken symlinks, wrong settings, missing files."""
    import configparser

    from .config import (
        build_token_context, expand_path, generated_path,
    )

    active_spec = get_active()
    if not active_spec:
        print("[FAIL] No active palette set.")
        return 1

    name, hint = parse_palette_spec(active_spec)
    try:
        palette  = load_palette(name)
        registry = load_registry()
    except Exception as e:
        print(f"[FAIL] Cannot load palette/registry: {e}")
        return 1

    variant = resolve_variant(palette, hint)
    issues  = 0

    def ok(msg: str) -> None:
        print(f"  [OK]    {msg}")

    def drift(msg: str) -> None:
        nonlocal issues
        issues += 1
        print(f"  [DRIFT] {msg}")

    print(f"Checking: {name}:{variant}\n")

    seen_templates: set[str] = set()
    for app in registry["app"]:
        for fe in app["files"]:
            tmpl_rel = fe["template"]
            if tmpl_rel in seen_templates:
                continue
            seen_templates.add(tmpl_rel)
            gen = generated_path(name, variant, tmpl_rel)
            if gen.exists():
                ok(f"generated: {tmpl_rel}")
            else:
                drift(f"generated file missing: {gen}")

    for app in registry["app"]:
        for fe in app["files"]:
            output_str = fe.get("output", "")
            if not output_str or fe.get("copy"):
                continue
            dest = expand_path(output_str)
            tmpl_rel = fe["template"]
            expected_target = generated_path(name, variant, tmpl_rel)
            if not dest.exists() and not dest.is_symlink():
                drift(f"symlink missing: {dest}")
            elif dest.is_symlink():
                actual = dest.resolve()
                if actual == expected_target.resolve():
                    ok(f"symlink: {dest.name} → {tmpl_rel}")
                else:
                    drift(f"symlink wrong target: {dest.name} → {actual} (expected {expected_target})")
            else:
                drift(f"not a symlink: {dest} (was it overwritten?)")

    kvconfig = expand_path("~/.config/Kvantum/kvantum.kvconfig")
    if kvconfig.exists():
        if "theme=themr-generated" in kvconfig.read_text():
            ok("kvantum.kvconfig: theme=themr-generated")
        else:
            drift("kvantum.kvconfig: active theme is not themr-generated")
    else:
        drift("kvantum.kvconfig: file missing")

    mode = palette.get(variant, {}).get("_mode") or palette.get("_mode", "dark")
    dark = mode == "dark"
    expected_pref  = "1" if dark else "0"
    expected_theme = "adw-gtk3-dark" if dark else "adw-gtk3"
    for ini_path_str in ("~/.config/gtk-3.0/settings.ini", "~/.config/gtk-4.0/settings.ini"):
        ini_path = expand_path(ini_path_str)
        if not ini_path.exists():
            continue
        cfg = configparser.ConfigParser()
        cfg.optionxform = str
        cfg.read(ini_path)
        s = cfg["Settings"] if cfg.has_section("Settings") else {}
        pref  = s.get("gtk-application-prefer-dark-theme", "")
        theme = s.get("gtk-theme-name", "")
        if pref == expected_pref and theme == expected_theme:
            ok(f"{ini_path.parent.name}/settings.ini: theme={theme}, dark={pref}")
        else:
            drift(
                f"{ini_path.parent.name}/settings.ini: "
                f"theme={theme!r} (want {expected_theme!r}), "
                f"dark={pref!r} (want {expected_pref!r})"
            )

    print()
    if issues == 0:
        print("All checks passed.")
        return 0
    else:
        print(f"{issues} issue(s) found. Run 'sauce repair' to restore all managed files.")
        return 1


def cmd_repair(_args: list[str]) -> int:
    """Re-apply the active theme with force-regeneration to fix any drift."""
    active = get_active()
    if not active:
        print("error: no active palette set", file=sys.stderr)
        return 1
    name, hint = parse_palette_spec(active)
    generate_palette(name, hint, force=True)
    return 0 if switch_palette(active, reload=True) else 1


def cmd_switch_qs(args: list[str]) -> int:
    reload = "--no-reload" not in args
    args   = [a for a in args if a != "--no-reload"]

    if not args:
        print("Usage: sauce switch-qs <qs_name> [--no-reload]")
        return 1
    spec = find_spec_by_qs_name(args[0])
    if spec is None:
        print(f"error: no palette with _qs_name '{args[0]}'", file=sys.stderr)
        return 1
    return 0 if switch_palette(spec, reload=reload) else 1


def cmd_init(_args: list[str]) -> int:
    """Bootstrap ~/.config/themr/ from bundled package data."""
    import importlib.resources
    import shutil

    data_pkg = importlib.resources.files("sauce") / "data"

    def _copy_tree(src_pkg, dest: "Path") -> int:  # type: ignore[name-defined]
        """Recursively copy package data to dest; never overwrites existing files."""
        copied = 0
        dest.mkdir(parents=True, exist_ok=True)
        for item in src_pkg.iterdir():
            target = dest / item.name
            if item.is_dir():
                copied += _copy_tree(item, target)
            else:
                if not target.exists():
                    target.write_bytes(item.read_bytes())
                    copied += 1
        return copied

    SAUCE_DIR.mkdir(parents=True, exist_ok=True)

    # registry.toml
    reg_src = data_pkg / "registry.toml"
    reg_dst = SAUCE_DIR / "registry.toml"
    if not reg_dst.exists():
        reg_dst.write_bytes(reg_src.read_bytes())
        print(f"  created: {reg_dst}")
    else:
        print(f"  exists:  {reg_dst} (skipped)")

    # palettes/
    n_pal = _copy_tree(data_pkg / "palettes", PALETTES_DIR)
    print(f"  palettes: {n_pal} new file(s) copied to {PALETTES_DIR}")

    # templates/
    n_tmpl = _copy_tree(data_pkg / "templates", TEMPLATES_DIR)
    print(f"  templates: {n_tmpl} new file(s) copied to {TEMPLATES_DIR}")

    print(f"\nInit complete. Run: sauce generate --all && sauce switch nord")
    return 0


def cmd_dynamic(args: list[str]) -> int:
    variant = "dark"
    remaining = []
    for a in args:
        if a in ("--dark", "--light"):
            variant = a.lstrip("-")
        else:
            remaining.append(a)

    if not remaining:
        print("Usage: sauce dynamic <image_path> [--dark|--light]")
        return 1

    from .dynamic import run_dynamic
    return 0 if run_dynamic(remaining[0], variant=variant) else 1


def cmd_gui(args: list[str]) -> int:
    """Launch the PySide6 GUI. Requires: pip install sauce[gui]"""
    palette = None
    for i, a in enumerate(args):
        if a in ("--palette", "-p") and i + 1 < len(args):
            palette = args[i + 1]

    try:
        from .gui.app import run
    except ImportError:
        print(
            "error: GUI dependencies not installed.\n"
            "       Run: pip install sauce[gui]",
            file=sys.stderr,
        )
        return 1

    run(palette)
    return 0


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

COMMANDS = {
    "generate":  cmd_generate,
    "switch":    cmd_switch,
    "switch-qs": cmd_switch_qs,
    "list":      cmd_list,
    "current":   cmd_current,
    "validate":  cmd_validate,
    "doctor":    cmd_doctor,
    "repair":    cmd_repair,
    "init":      cmd_init,
    "dynamic":   cmd_dynamic,
    "gui":       cmd_gui,
}


HELP = """\
Usage: sauce <command> [args...]

Commands:
  switch   <palette>[:<variant>] [--no-reload]
           Apply a palette (resolves default variant if omitted).

  list     Show all palettes with their variants; marks the active one.

  current  Print the active palette spec (e.g. nord:dark).

  generate [<palette>[:<variant>] | --all] [--force]
           Render templates to generated/.

  switch-qs <qs_name> [--no-reload]
           Apply a palette by its _qs_name (used by Quickshell).

  validate Check that all palettes × variants × templates resolve cleanly.

  doctor   Check active theme for drift (broken symlinks, wrong GTK/Kvantum settings).

  repair   Re-apply the active theme with force-regeneration to fix any drift.

  init     Bootstrap ~/.config/themr/ from bundled package data.
           Safe to run repeatedly — never overwrites existing user files.

  dynamic  <image_path> [--dark|--light]
           Generate and apply a wallpaper-driven palette via matugen.
           Writes palettes/dynamic.json, overwrites on each call.
           Example: sauce dynamic ~/wallpapers/forest.jpg

  gui      [--palette <name>]
           Launch the PySide6 GUI palette editor.
           Requires: pip install sauce[gui]

  help     Show this message.
"""


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help", "help"):
        print(HELP, end="")
        sys.exit(0)

    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'. Run 'sauce help' for usage.", file=sys.stderr)
        sys.exit(1)

    sys.exit(COMMANDS[cmd](args[1:]))
