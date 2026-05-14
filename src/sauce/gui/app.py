"""sauce.gui.app — QApplication entry point."""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ..config import get_active, load_palette, parse_palette_spec, resolve_variant
from .stylesheet import generate_stylesheet


def _active_colors() -> dict:
    """Return the color dict for the currently active palette, or empty dict."""
    spec = get_active()
    if not spec:
        return {}
    try:
        name, hint = parse_palette_spec(spec)
        palette    = load_palette(name)
        variant    = resolve_variant(palette, hint)
        return palette.get(variant, {})
    except Exception:
        return {}


def run(initial_palette: str | None = None) -> None:
    """Launch the GUI, optionally pre-loading a specific palette."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Sauce")
    app.setApplicationVersion("2.0.0")

    # Apply self-theming stylesheet from active palette
    colors = _active_colors()
    if colors:
        app.setStyleSheet(generate_stylesheet(colors))

    # Lazy import to keep startup fast
    from .window import MainWindow

    window = MainWindow(initial_palette)
    window.show()

    # Re-apply stylesheet when the window signals a theme was applied
    window.theme_applied.connect(lambda colors: app.setStyleSheet(generate_stylesheet(colors)))

    sys.exit(app.exec())
