"""sauce.render — Template rendering and generation."""

import re
import sys
from pathlib import Path

from .config import (
    GENERATED_DIR, PALETTES_DIR, TEMPLATES_DIR,
    build_token_context, generated_path, list_palettes, load_palette,
    load_registry, palette_variants, resolve_variant,
)

# Matches {{token}} where token is all-lowercase letters/digits/underscores,
# first char must be a letter. Safe from OMP Go-template syntax which uses
# spaces, dots, or uppercase ({{ .Path }}, {{.Icon}}, etc.).
TOKEN_RE = re.compile(r'\{\{([a-z][a-z0-9_]*)\}\}')


def render_template(template_path: Path, tokens: dict) -> str:
    """Render a template file, substituting all {{token}} occurrences."""
    text = template_path.read_text()

    def replace(m: re.Match) -> str:
        key = m.group(1)
        if key not in tokens:
            raise KeyError(f"Template token '{{{{{key}}}}}' not found in palette context")
        return tokens[key]

    return TOKEN_RE.sub(replace, text)


def is_up_to_date(palette_path: Path, generated_file: Path) -> bool:
    """True if generated_file exists and is newer than the palette JSON."""
    return (
        generated_file.exists()
        and generated_file.stat().st_mtime >= palette_path.stat().st_mtime
    )


def generate_palette(name: str, variant: str | None = None, force: bool = False) -> bool:
    """
    Render all templates for a single palette.

    If variant is None, generates all variants in the palette.
    Deduplicates template paths so shared templates are only rendered once per variant.
    """
    palette_path = PALETTES_DIR / f"{name}.json"
    if not palette_path.exists():
        print(f"  error: palette not found: {palette_path}", file=sys.stderr)
        return False

    try:
        palette  = load_palette(name)
        registry = load_registry()
    except Exception as e:
        print(f"  error loading palette/registry: {e}", file=sys.stderr)
        return False

    variants = [resolve_variant(palette, variant)] if variant else palette_variants(palette)
    if not variants:
        print(f"  error: no variants found in {name}", file=sys.stderr)
        return False

    # Collect unique template paths from registry
    unique_templates: list[str] = []
    seen: set[str] = set()
    for app in registry["app"]:
        for file_entry in app["files"]:
            tmpl_rel = file_entry["template"]
            if tmpl_rel not in seen:
                seen.add(tmpl_rel)
                unique_templates.append(tmpl_rel)

    ok = True
    for v in variants:
        try:
            tokens = build_token_context(palette, v)
        except Exception as e:
            print(f"  error building tokens for {name}:{v}: {e}", file=sys.stderr)
            ok = False
            continue

        # Freshness check: skip if sentinel generated file is newer than palette
        if not force and unique_templates:
            sentinel = generated_path(name, v, unique_templates[0])
            if is_up_to_date(palette_path, sentinel):
                print(f"  {name}:{v}: up to date")
                continue

        rendered = 0
        for tmpl_rel in unique_templates:
            tmpl_path = TEMPLATES_DIR / tmpl_rel
            gen_path  = generated_path(name, v, tmpl_rel)
            if not tmpl_path.exists():
                print(f"  warning: template not found: {tmpl_path}", file=sys.stderr)
                continue
            gen_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                gen_path.write_text(render_template(tmpl_path, tokens))
                rendered += 1
            except KeyError as e:
                print(f"  error rendering {tmpl_path.name} for {name}:{v}: {e}", file=sys.stderr)
                ok = False

        print(f"  {name}:{v}: generated {rendered} files → {GENERATED_DIR / name / v}")

    return ok


def generate_all(force: bool = False) -> bool:
    palettes = list_palettes()
    if not palettes:
        print(f"No palettes found in {PALETTES_DIR}", file=sys.stderr)
        return False
    print(f"Generating {len(palettes)} palettes...")
    return all(generate_palette(p, force=force) for p in palettes)
