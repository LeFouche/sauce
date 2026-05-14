"""sauce.gui.palette_list — Left sidebar: palette list with swatch strips."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from ..config import get_active, list_palettes, load_palette, palette_variants, parse_palette_spec

# 5 roles shown in the swatch strip (left to right)
_SWATCH_ROLES = ("bg", "cyan", "green", "orange", "pink")
_SWATCH_FALLBACKS = ("#1e1e2e", "#89dceb", "#a6e3a1", "#fab387", "#f5c2e7")
_SWATCH_W = 20
_SWATCH_H = 20
_SWATCH_GAP = 3
_ROW_H = 52


class _PaletteRow(QWidget):
    """Single row in the palette list."""

    clicked    = Signal(str)   # palette stem
    edit_clicked = Signal(str) # palette stem

    def __init__(self, stem: str, display_name: str, swatches: list[str], is_active: bool) -> None:
        super().__init__()
        self.stem = stem
        self.setFixedHeight(_ROW_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(8)

        # Active dot
        self._dot = QLabel("●" if is_active else "○")
        self._dot.setFixedWidth(14)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot.setStyleSheet(
            f"color: {'#a6e3a1' if is_active else 'transparent'}; font-size: 10px;"
        )
        layout.addWidget(self._dot)

        # Name
        lbl = QLabel(display_name)
        lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(lbl)

        layout.addStretch()

        # Swatch strip
        swatch_widget = _SwatchStrip(swatches)
        layout.addWidget(swatch_widget)

        # Edit button (hidden, shown on hover)
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedSize(46, 24)
        self._edit_btn.setStyleSheet("font-size: 11px; padding: 0;")
        self._edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_btn.hide()
        self._edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self.stem))
        layout.addWidget(self._edit_btn)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.stem)

    def enterEvent(self, event) -> None:
        self._edit_btn.show()

    def leaveEvent(self, event) -> None:
        self._edit_btn.hide()

    def set_active(self, active: bool) -> None:
        self._dot.setText("●" if active else "○")
        self._dot.setStyleSheet(
            f"color: {'#a6e3a1' if active else 'transparent'}; font-size: 10px;"
        )


class _SwatchStrip(QWidget):
    """Five colored squares."""

    def __init__(self, colors: list[str]) -> None:
        super().__init__()
        self._colors = colors
        w = len(colors) * (_SWATCH_W + _SWATCH_GAP) - _SWATCH_GAP
        self.setFixedSize(w, _SWATCH_H)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = 0
        for hex_color in self._colors:
            color = QColor(hex_color) if hex_color else QColor("#888888")
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(x, 0, _SWATCH_W, _SWATCH_H, 4, 4)
            x += _SWATCH_W + _SWATCH_GAP


def _extract_swatches(palette: dict) -> list[str]:
    """Extract 5 representative colors from the palette's default variant."""
    variants = [k for k in palette if not k.startswith("_")]
    if not variants:
        return list(_SWATCH_FALLBACKS)
    default = palette.get("_default_variant") or variants[0]
    vdata   = palette.get(default, {})
    return [
        vdata.get(role, fb)
        for role, fb in zip(_SWATCH_ROLES, _SWATCH_FALLBACKS)
    ]


class PaletteListPanel(QWidget):
    """
    Left sidebar: search field + scrollable palette list + New Palette button.

    Signals
    -------
    palette_selected(stem: str)  — user clicked a palette row
    new_requested()              — user clicked New Palette
    """

    palette_selected = Signal(str)
    new_requested    = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(180)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(48)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_lbl = QLabel("Palettes")
        header_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")
        header_layout.addWidget(header_lbl)
        header_layout.addStretch()
        layout.addWidget(header)

        # ── Search ───────────────────────────────────────────────────────────
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedHeight(32)
        self._search.setContentsMargins(0, 0, 0, 0)
        search_wrapper = QWidget()
        sw_layout = QHBoxLayout(search_wrapper)
        sw_layout.setContentsMargins(8, 0, 8, 8)
        sw_layout.addWidget(self._search)
        layout.addWidget(search_wrapper)
        self._search.textChanged.connect(self._filter)

        # ── Separator ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        # ── Palette list ─────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setFrameShape(QFrame.Shape.NoFrame)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSpacing(0)
        layout.addWidget(self._list)

        # ── New palette button ────────────────────────────────────────────────
        new_btn = QPushButton("+ New Palette")
        new_btn.setFixedHeight(40)
        new_btn.setProperty("class", "accent")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setContentsMargins(12, 0, 12, 0)
        btn_wrapper = QWidget()
        bw_layout = QHBoxLayout(btn_wrapper)
        bw_layout.setContentsMargins(8, 8, 8, 12)
        bw_layout.addWidget(new_btn)
        layout.addWidget(btn_wrapper)
        new_btn.clicked.connect(self.new_requested)

        # ── Load data ────────────────────────────────────────────────────────
        self._rows: dict[str, _PaletteRow] = {}
        self._selected: str | None = None
        self.reload()

    # ── Public interface ─────────────────────────────────────────────────────

    def reload(self) -> None:
        """Refresh the list from disk."""
        self._list.clear()
        self._rows.clear()
        active_spec = get_active()
        active_stem = parse_palette_spec(active_spec)[0] if active_spec else None

        for stem in list_palettes():
            try:
                palette     = load_palette(stem)
                display_name = palette.get("_name", stem)
                swatches    = _extract_swatches(palette)
            except Exception:
                display_name = stem
                swatches    = list(_SWATCH_FALLBACKS)

            is_active = stem == active_stem
            row = _PaletteRow(stem, display_name, swatches, is_active)
            row.clicked.connect(self._on_row_clicked)
            row.edit_clicked.connect(self._on_row_clicked)

            item = QListWidgetItem()
            item.setSizeHint(QSize(0, _ROW_H))
            item.setData(Qt.ItemDataRole.UserRole, stem)
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            self._rows[stem] = row

    def select_palette(self, stem: str) -> None:
        """Programmatically select a palette (does not emit signal)."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == stem:
                self._list.setCurrentItem(item)
                self._selected = stem
                break

    # ── Private ──────────────────────────────────────────────────────────────

    def _on_row_clicked(self, stem: str) -> None:
        self._selected = stem
        self.select_palette(stem)
        self.palette_selected.emit(stem)

    def _filter(self, text: str) -> None:
        text = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item is None:
                continue
            stem = item.data(Qt.ItemDataRole.UserRole)
            item.setHidden(bool(text) and text not in stem.lower())
