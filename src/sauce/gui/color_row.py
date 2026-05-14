"""sauce.gui.color_row — Single color role row: swatch + label + hex field + HSV popover + picker."""

import re

from PySide6.QtCore import QPoint, QRegularExpression, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QColorDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSlider, QVBoxLayout, QWidget,
)

_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


class _Swatch(QFrame):
    """Clickable colored square."""
    clicked = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(24, 24)
        self._color = QColor("#888888")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_color(self, hex_color: str) -> None:
        c = QColor(hex_color)
        if c.isValid():
            self._color = c
            self.update()

    def mousePressEvent(self, event) -> None:
        self.clicked.emit()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(self.rect(), 5, 5)


class _HsvPopover(QWidget):
    """Compact HSV slider popover shown below the mini-bar."""

    color_changed = Signal(str)  # hex

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFixedWidth(220)
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self._h_slider = self._make_slider(0, 359, "H")
        self._s_slider = self._make_slider(0, 255, "S")
        self._v_slider = self._make_slider(0, 255, "V")

        for slider, label in zip(
            (self._h_slider, self._s_slider, self._v_slider), ("H", "S", "V")
        ):
            row = QWidget()
            rl  = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(6)
            lbl = QLabel(label)
            lbl.setFixedWidth(12)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(lbl)
            rl.addWidget(slider)
            layout.addWidget(row)

        self._h_slider.valueChanged.connect(self._emit)
        self._s_slider.valueChanged.connect(self._emit)
        self._v_slider.valueChanged.connect(self._emit)

    def _make_slider(self, lo: int, hi: int, _: str) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setFixedHeight(20)
        return s

    def set_color(self, hex_color: str) -> None:
        c = QColor(hex_color)
        if not c.isValid():
            return
        self._updating = True
        self._h_slider.setValue(c.hsvHue() if c.hsvHue() >= 0 else 0)
        self._s_slider.setValue(c.hsvSaturation())
        self._v_slider.setValue(c.value())
        self._updating = False

    def _emit(self) -> None:
        if self._updating:
            return
        c = QColor.fromHsv(
            self._h_slider.value(),
            self._s_slider.value(),
            self._v_slider.value(),
        )
        self.color_changed.emit(c.name())


class _HsvMiniBar(QWidget):
    """Three-segment H/S/V bar. Click to open the HSV popover."""

    color_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(90, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color = QColor("#888888")
        self._popover: _HsvPopover | None = None

    def set_color(self, hex_color: str) -> None:
        c = QColor(hex_color)
        if c.isValid():
            self._color = c
            self.update()

    def mousePressEvent(self, event) -> None:
        if self._popover is None:
            self._popover = _HsvPopover(self)
            self._popover.color_changed.connect(self.color_changed)
        self._popover.set_color(self._color.name())
        pos = self.mapToGlobal(QPoint(0, self.height() + 2))
        self._popover.move(pos)
        self._popover.show()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        h  = self._color.hsvHue() if self._color.hsvHue() >= 0 else 0
        s  = self._color.hsvSaturation()
        v  = self._color.value()
        w  = self.width()
        ht = self.height()
        seg_w = (w - 4) // 3

        segments = [
            (QColor.fromHsv(h, 200, 180), "H"),
            (QColor.fromHsv(h, s, 180),   "S"),
            (QColor.fromHsv(h, s, v),     "V"),
        ]
        x = 0
        for i, (color, _) in enumerate(segments):
            sw = seg_w if i < 2 else w - x
            p.setBrush(color)
            p.setPen(Qt.PenStyle.NoPen)
            if i == 0:
                # Left rounded
                p.drawRoundedRect(x, 0, sw + 4, ht, 3, 3)
                p.setBrush(color)
                p.drawRect(x + sw - 4, 0, 8, ht)
            elif i == 2:
                # Right rounded
                p.drawRoundedRect(x, 0, sw, ht, 3, 3)
                p.setBrush(color)
                p.drawRect(x, 0, 4, ht)
            else:
                p.drawRect(x, 0, sw + 2, ht)
            x += sw + 2


class ColorRow(QWidget):
    """
    [swatch 24px] [label 100px] [hex 90px] [HSV bar 90px] [🎨 28px]

    Signals
    -------
    color_changed(role: str, hex: str)
    """

    color_changed = Signal(str, str)

    def __init__(self, role: str, label: str) -> None:
        super().__init__()
        self.role = role
        self._hex = "#888888"
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # Swatch
        self._swatch = _Swatch()
        self._swatch.clicked.connect(self._open_picker)
        layout.addWidget(self._swatch)

        # Label
        lbl = QLabel(label)
        lbl.setFixedWidth(100)
        lbl.setStyleSheet("font-size: 12px;")
        layout.addWidget(lbl)

        # Hex field
        self._hex_edit = QLineEdit()
        self._hex_edit.setFixedWidth(80)
        self._hex_edit.setFixedHeight(26)
        self._hex_edit.setMaxLength(7)
        self._hex_edit.setPlaceholderText("#rrggbb")
        self._hex_edit.setStyleSheet("font-family: monospace; font-size: 12px;")
        validator = QRegularExpressionValidator(QRegularExpression(r'^#?[0-9a-fA-F]{0,6}$'))
        self._hex_edit.setValidator(validator)
        self._hex_edit.textEdited.connect(self._on_hex_edited)
        layout.addWidget(self._hex_edit)

        # HSV mini-bar
        self._hsv_bar = _HsvMiniBar()
        self._hsv_bar.color_changed.connect(self._on_hsv_changed)
        layout.addWidget(self._hsv_bar)

        # Picker button
        pick_btn = QPushButton("🎨")
        pick_btn.setFixedSize(28, 26)
        pick_btn.setStyleSheet("font-size: 14px; padding: 0; border: none; background: transparent;")
        pick_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pick_btn.clicked.connect(self._open_picker)
        layout.addWidget(pick_btn)

        layout.addStretch()

    def set_color(self, hex_color: str) -> None:
        """Set the displayed color without emitting color_changed."""
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color
        self._hex = hex_color
        self._hex_edit.setText(hex_color)
        self._swatch.set_color(hex_color)
        self._hsv_bar.set_color(hex_color)

    def _on_hex_edited(self, text: str) -> None:
        if not text.startswith("#"):
            text = "#" + text
        if _HEX_RE.match(text):
            self._hex = text
            self._swatch.set_color(text)
            self._hsv_bar.set_color(text)
            self.color_changed.emit(self.role, text)

    def _on_hsv_changed(self, hex_color: str) -> None:
        self._hex = hex_color
        self._hex_edit.setText(hex_color)
        self._swatch.set_color(hex_color)
        self.color_changed.emit(self.role, hex_color)

    def _open_picker(self) -> None:
        initial = QColor(self._hex)
        color   = QColorDialog.getColor(
            initial, self, f"Pick color",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if color.isValid():
            hex_color = color.name()
            self.set_color(hex_color)
            self.color_changed.emit(self.role, hex_color)
