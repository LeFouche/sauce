"""sauce.gui.stylesheet — Generate a Qt stylesheet from a palette variant dict.

The colors dict is the raw variant data from the palette JSON
(keys: bg, bg1, bg2, fg, fg1, subtext, red, orange, yellow, green, cyan,
blue, purple, pink, teal).
"""


def _c(colors: dict, *keys: str, fallback: str = "#1e1e2e") -> str:
    """Return the first key found in colors, or fallback."""
    for k in keys:
        v = colors.get(k)
        if v:
            return v
    return fallback


def generate_stylesheet(colors: dict) -> str:
    bg      = _c(colors, "bg",      fallback="#1e1e2e")
    surface = _c(colors, "bg1",     fallback="#313244")
    overlay = _c(colors, "bg2",     fallback="#45475a")
    text    = _c(colors, "fg",      fallback="#cdd6f4")
    subtext = _c(colors, "subtext", "fg1", fallback="#bac2de")
    accent  = _c(colors, "cyan",    fallback="#89dceb")
    green   = _c(colors, "green",   fallback="#a6e3a1")
    red     = _c(colors, "red",     fallback="#f38ba8")
    orange  = _c(colors, "orange",  fallback="#fab387")

    return f"""
/* ── Base ─────────────────────────────────────────────────── */
QWidget {{
    background-color: {bg};
    color: {text};
    font-family: "Noto Sans", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

QMainWindow {{
    background-color: {bg};
}}

/* ── Scroll areas ──────────────────────────────────────────── */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: {bg};
    width: 6px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {overlay};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* ── Splitter ──────────────────────────────────────────────── */
QSplitter::handle {{
    background: {overlay};
    width: 1px;
    height: 1px;
}}

/* ── Labels ────────────────────────────────────────────────── */
QLabel {{
    background: transparent;
    color: {text};
}}
QLabel[class="subtext"] {{
    color: {subtext};
    font-size: 11px;
}}
QLabel[class="section-header"] {{
    color: {subtext};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}

/* ── Line edits ────────────────────────────────────────────── */
QLineEdit {{
    background-color: {surface};
    color: {text};
    border: 1px solid {overlay};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {accent};
    selection-color: {bg};
}}
QLineEdit:focus {{
    border-color: {accent};
}}
QLineEdit:disabled {{
    color: {subtext};
    background-color: {bg};
}}

/* ── Push buttons ──────────────────────────────────────────── */
QPushButton {{
    background-color: {surface};
    color: {text};
    border: 1px solid {overlay};
    border-radius: 6px;
    padding: 5px 14px;
    min-height: 26px;
}}
QPushButton:hover {{
    background-color: {overlay};
    border-color: {accent};
}}
QPushButton:pressed {{
    background-color: {accent};
    color: {bg};
    border-color: {accent};
}}
QPushButton:disabled {{
    color: {subtext};
    border-color: {overlay};
}}
QPushButton[class="accent"] {{
    background-color: {accent};
    color: {bg};
    border-color: {accent};
    font-weight: 600;
}}
QPushButton[class="accent"]:hover {{
    background-color: {green};
    border-color: {green};
}}
QPushButton[class="danger"] {{
    background-color: transparent;
    color: {red};
    border-color: {red};
}}
QPushButton[class="danger"]:hover {{
    background-color: {red};
    color: {bg};
}}

/* ── List view ─────────────────────────────────────────────── */
QListWidget, QListView {{
    background-color: {surface};
    border: none;
    border-radius: 8px;
    outline: none;
}}
QListWidget::item, QListView::item {{
    padding: 6px 10px;
    border-radius: 6px;
    margin: 1px 4px;
    color: {text};
}}
QListWidget::item:selected, QListView::item:selected {{
    background-color: {overlay};
    color: {text};
}}
QListWidget::item:hover, QListView::item:hover {{
    background-color: {overlay};
}}

/* ── Tab bar ───────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {subtext};
    padding: 5px 12px;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    color: {text};
    border-bottom-color: {accent};
}}
QTabBar::tab:hover {{
    color: {text};
}}

/* ── Combo box ─────────────────────────────────────────────── */
QComboBox {{
    background-color: {surface};
    color: {text};
    border: 1px solid {overlay};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 26px;
}}
QComboBox:focus {{
    border-color: {accent};
}}
QComboBox QAbstractItemView {{
    background-color: {surface};
    color: {text};
    border: 1px solid {overlay};
    selection-background-color: {overlay};
}}

/* ── Tooltips ──────────────────────────────────────────────── */
QToolTip {{
    background-color: {overlay};
    color: {text};
    border: 1px solid {overlay};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ── Status bar ────────────────────────────────────────────── */
QStatusBar {{
    background-color: {surface};
    color: {subtext};
    border-top: 1px solid {overlay};
}}

/* ── Menu bar ──────────────────────────────────────────────── */
QMenuBar {{
    background-color: {surface};
    color: {text};
    border-bottom: 1px solid {overlay};
}}
QMenuBar::item:selected {{
    background-color: {overlay};
}}
QMenu {{
    background-color: {surface};
    color: {text};
    border: 1px solid {overlay};
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {overlay};
}}
QMenu::separator {{
    height: 1px;
    background: {overlay};
    margin: 4px 8px;
}}
"""
