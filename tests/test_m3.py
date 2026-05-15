from sauce.config import _adjust_lightness


def test_adjust_lightness_darkens():
    result = _adjust_lightness("#ffffff", -0.3)
    assert result.startswith("#")
    h = result.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    assert r < 255 and g < 255 and b < 255


def test_adjust_lightness_lightens():
    result = _adjust_lightness("#000000", 0.3)
    h = result.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    assert r > 0 or g > 0 or b > 0


def test_adjust_lightness_clamps_to_1():
    result = _adjust_lightness("#ffffff", 1.0)
    assert result == "#ffffff"


def test_adjust_lightness_clamps_to_0():
    result = _adjust_lightness("#000000", -1.0)
    assert result == "#000000"


def test_adjust_lightness_preserves_hue():
    result = _adjust_lightness("#ff0000", -0.2)
    h = result.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    assert r > g and r > b  # still reddish


from sauce.config import build_m3_context, build_token_context, load_palette


_DARK_TOKENS = {
    "mode": "dark",
    "bg": "#1e1e2e", "bg1": "#313244", "bg2": "#45475a",
    "fg": "#cdd6f4", "fg1": "#6c7086", "subtext": "#a6adc8",
    "red": "#f38ba8", "blue": "#89b4fa", "teal": "#94e2d5",
    "purple": "#b4befe",
}

_LIGHT_TOKENS = {
    "mode": "light",
    "bg": "#eff1f5", "bg1": "#e6e9ef", "bg2": "#ccd0da",
    "fg": "#4c4f69", "fg1": "#9ca0b0", "subtext": "#6c6f85",
    "red": "#d20f39", "blue": "#1e66f5", "teal": "#179299",
    "purple": "#7287fd",
}


def test_m3_context_has_primary_token():
    m3 = build_m3_context(_DARK_TOKENS)
    assert "m3_primary" in m3
    assert m3["m3_primary"] == "#89b4fa"  # blue → primary


def test_m3_context_has_hex_variants():
    m3 = build_m3_context(_DARK_TOKENS)
    for key in list(m3.keys()):
        if not key.endswith("_hex"):
            assert f"{key}_hex" in m3, f"missing {key}_hex"


def test_m3_context_dark_on_primary_is_white():
    m3 = build_m3_context(_DARK_TOKENS)
    assert m3["m3_on_primary"] == "#ffffff"


def test_m3_context_light_on_primary_is_black():
    m3 = build_m3_context(_LIGHT_TOKENS)
    assert m3["m3_on_primary"] == "#000000"


def test_m3_context_background_maps_bg():
    m3 = build_m3_context(_DARK_TOKENS)
    assert m3["m3_background"] == "#1e1e2e"


def test_m3_context_surface_maps_bg1():
    m3 = build_m3_context(_DARK_TOKENS)
    assert m3["m3_surface"] == "#313244"


def test_m3_context_outline_maps_subtext():
    m3 = build_m3_context(_DARK_TOKENS)
    assert m3["m3_outline"] == "#a6adc8"


def test_m3_tokens_injected_into_build_token_context(data_dir):
    palette = load_palette("test")
    tokens = build_token_context(palette, "dark")
    assert "m3_primary" in tokens
    assert "m3_background" in tokens
    assert "m3_surface_hex" in tokens
