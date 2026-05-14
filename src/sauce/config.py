"""sauce.config — paths, palette loading, and token context."""

import json
import os
import tomllib
from pathlib import Path

# ---------------------------------------------------------------------------
# Directory resolution — honours SAUCE_DATA_DIR (testing) and XDG_CONFIG_HOME
# ---------------------------------------------------------------------------

def _resolve_sauce_dir() -> Path:
    override = os.environ.get("SAUCE_DATA_DIR", "")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "themr"   # runtime path unchanged this release


SAUCE_DIR     = _resolve_sauce_dir()
PALETTES_DIR  = SAUCE_DIR / "palettes"
TEMPLATES_DIR = SAUCE_DIR / "templates"
GENERATED_DIR = SAUCE_DIR / "generated"
REGISTRY_PATH = SAUCE_DIR / "registry.toml"
ACTIVE_FILE   = SAUCE_DIR / "active"

# ---------------------------------------------------------------------------
# Color roles — authoritative schema used by render, GUI, and validation
# ---------------------------------------------------------------------------

COLOR_ROLES = {
    "bg", "bg1", "bg2",
    "fg", "fg1", "subtext",
    "red", "orange", "yellow", "green",
    "cyan", "blue", "purple", "pink", "teal",
}

# Human-friendly labels for the GUI, in display order
COLOR_ROLE_LABELS: list[tuple[str, str]] = [
    # (role_key, display_label)
    ("bg",      "Background"),
    ("bg1",     "Surface"),
    ("bg2",     "Overlay"),
    ("fg",      "Text"),
    ("fg1",     "Subtext alt"),
    ("subtext", "Subtext"),
    ("red",     "Red / Error"),
    ("orange",  "Orange / Peach"),
    ("yellow",  "Yellow / Sun"),
    ("green",   "Green / Mint"),
    ("cyan",    "Cyan / Sky"),
    ("blue",    "Blue"),
    ("purple",  "Purple / Lavender"),
    ("pink",    "Pink / Rose"),
    ("teal",    "Teal / Aqua"),
]

# Group structure for the GUI editor panels
COLOR_ROLE_GROUPS: list[tuple[str, list[str]]] = [
    ("Backgrounds",  ["bg", "bg1", "bg2"]),
    ("Text",         ["fg", "fg1", "subtext"]),
    ("Accents",      ["cyan", "green", "purple", "orange", "yellow", "pink", "teal"]),
    ("Semantic",     ["red", "blue"]),
]


# ---------------------------------------------------------------------------
# Registry & palette loading
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    with open(REGISTRY_PATH, "rb") as f:
        return tomllib.load(f)


def load_palette(name: str) -> dict:
    """Load palette JSON by stem name. Raises FileNotFoundError if missing."""
    path = PALETTES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Palette not found: {path}")
    return json.loads(path.read_text())


def parse_palette_spec(spec: str) -> tuple[str, str | None]:
    """Parse 'palette[:variant]' → (name, variant_hint or None)."""
    if ":" in spec:
        name, variant = spec.split(":", 1)
        return name.strip(), variant.strip() or None
    return spec.strip(), None


def resolve_variant(palette: dict, hint: str | None) -> str:
    """Choose variant: hint → _default_variant → first available → 'dark'."""
    available = [k for k in palette if not k.startswith("_")]
    if hint and hint in available:
        return hint
    default = palette.get("_default_variant")
    if default and default in available:
        return default
    return available[0] if available else "dark"


def _detect_mode(hex_color: str) -> str:
    """Return 'dark' or 'light' based on the relative luminance of a hex color."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    # sRGB linearisation
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    luminance = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "dark" if luminance < 0.5 else "light"


def build_token_context(palette: dict, variant: str) -> dict:
    """
    Build the full substitution token dict from a palette + variant.

    For every color role k the context gets:
      {{k}}       → the hex value with #   (e.g. {{bg}} → #2e3440)
      {{k_hex}}   → the hex value without # (e.g. {{bg_hex}} → 2e3440)

    Aliases:
      text / text_hex    ← fg / fg_hex   (unless explicitly set)
      subtext            ← fg1           (unless explicitly set)
      error              ← red           (unless explicitly set)

    Top-level _* metadata and variant _* metadata are both included
    (leading underscore stripped); variant metadata wins on collision.
    """
    tokens: dict[str, str] = {}

    # Top-level metadata (_name, _author, _default_variant, …)
    for k, v in palette.items():
        if k.startswith("_") and v is not None:
            tokens[k[1:]] = str(v)

    variant_data = palette.get(variant, {})

    # Variant-level metadata — overrides top-level
    for k, v in variant_data.items():
        if k.startswith("_") and v is not None:
            tokens[k[1:]] = str(v)

    # Color roles
    for role in COLOR_ROLES:
        hex_val = variant_data.get(role)
        if hex_val:
            tokens[role] = hex_val
            tokens[f"{role}_hex"] = hex_val.lstrip("#")

    # text / subtext: alias fg / fg1 unless palette explicitly sets them
    if "text" not in tokens and "fg" in tokens:
        tokens["text"]     = tokens["fg"]
        tokens["text_hex"] = tokens["fg_hex"]
    if "subtext" not in tokens and "fg1" in tokens:
        tokens["subtext"]     = tokens["fg1"]
        tokens["subtext_hex"] = tokens["fg1_hex"]

    # error is a derived alias for red unless explicitly provided
    if "error" not in tokens and "red" in tokens:
        tokens["error"]     = tokens["red"]
        tokens["error_hex"] = tokens["red_hex"]

    # Computed convenience tokens derived from _mode (or auto-detected from bg luminance)
    mode = tokens.get("mode") or _detect_mode(tokens.get("bg", "#000000"))
    tokens["mode"] = mode
    tokens["mode_int"] = "1" if mode == "dark" else "0"
    tokens["vscodium_base_theme"] = (
        tokens.get("vscodium_theme") or
        ("Default Dark Modern" if mode == "dark" else "Default Light Modern")
    )

    return tokens


# ---------------------------------------------------------------------------
# Palette enumeration helpers
# ---------------------------------------------------------------------------

def find_spec_by_qs_name(qs_name: str) -> str | None:
    """
    Scan all palettes × variants for a matching _qs_name.
    Returns 'palette:variant', or None if not found.
    """
    for stem in list_palettes():
        try:
            palette = load_palette(stem)
        except Exception:
            continue
        for variant in palette_variants(palette):
            vdata = palette.get(variant, {})
            if vdata.get("_qs_name") == qs_name:
                return f"{stem}:{variant}"
    return None


def list_palettes() -> list[str]:
    """Return sorted palette stems, excluding _-prefixed names."""
    return sorted(
        p.stem for p in PALETTES_DIR.glob("*.json")
        if not p.stem.startswith("_")
    )


def palette_variants(palette: dict) -> list[str]:
    """Return the variant keys available in a palette dict."""
    return [k for k in palette if not k.startswith("_")]


def get_active() -> str | None:
    """Return the active palette spec (e.g. 'nord:dark'), or None."""
    if ACTIVE_FILE.exists():
        return ACTIVE_FILE.read_text().strip() or None
    return None


def set_active(spec: str) -> None:
    """Write the active palette spec to disk."""
    ACTIVE_FILE.write_text(spec)


def expand_path(p: str) -> Path:
    return Path(p).expanduser()


def generated_path(palette: str, variant: str, template_rel: str) -> Path:
    """
    Return the path where a rendered template lands.
    e.g. generated_path("nord", "dark", "gtk/colors.css")
         → ~/.config/themr/generated/nord/dark/gtk/colors.css
    """
    return GENERATED_DIR / palette / variant / template_rel
