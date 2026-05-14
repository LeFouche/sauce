"""sauce.gui.preview — Right panel: live QPainter mockup + swatch grid."""

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QFontMetrics
from PySide6.QtWidgets import (
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from ..config import COLOR_ROLE_LABELS
from ..switch import switch_palette


def _c(colors: dict, *keys: str, fallback: str = "#888888") -> QColor:
    for k in keys:
        v = colors.get(k)
        if v:
            c = QColor(v)
            if c.isValid():
                return c
    return QColor(fallback)


class _MockupWidget(QWidget):
    """QPainter-rendered mockup of a bar, terminal, and notification."""

    def __init__(self) -> None:
        super().__init__()
        self._colors: dict = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(260)

    def update_colors(self, colors: dict) -> None:
        self._colors = colors
        self.update()

    def paintEvent(self, event) -> None:
        if not self._colors:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        self._draw(p)

    def _draw(self, p: QPainter) -> None:
        c = self._colors
        W  = self.width()
        H  = self.height()
        PAD = 12

        bg      = _c(c, "bg",      fallback="#1e1e2e")
        surface = _c(c, "bg1",     fallback="#313244")
        overlay = _c(c, "bg2",     fallback="#45475a")
        text    = _c(c, "fg",      fallback="#cdd6f4")
        sub     = _c(c, "subtext", "fg1", fallback="#bac2de")
        cyan    = _c(c, "cyan",    fallback="#89dceb")
        green   = _c(c, "green",   fallback="#a6e3a1")
        orange  = _c(c, "orange",  fallback="#fab387")
        red     = _c(c, "red",     fallback="#f38ba8")
        purple  = _c(c, "purple",  fallback="#cba6f7")
        blue    = _c(c, "blue",    fallback="#89b4fa")
        teal    = _c(c, "teal",    fallback="#94e2d5")

        mono  = QFont("JetBrainsMono Nerd Font Mono", 9)
        sans  = QFont("Noto Sans", 10)
        small = QFont("Noto Sans", 8)

        # ── Background ───────────────────────────────────────────────────────
        p.fillRect(0, 0, W, H, bg)

        # ── Fake status bar (top) ────────────────────────────────────────────
        BAR_H = 24
        p.fillRect(PAD, PAD, W - PAD * 2, BAR_H, surface)
        self._rounded_rect(p, PAD, PAD, W - PAD * 2, BAR_H, 6, surface)

        # Workspace dots
        x = PAD + 10
        for i, dot_color in enumerate([cyan, green, orange]):
            p.setBrush(dot_color if i == 0 else overlay)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(x, PAD + 8, 8, 8)
            x += 14

        # Clock (center)
        p.setFont(small)
        p.setPen(sub)
        clock_text = "12:34"
        fm = QFontMetrics(small)
        cx = PAD + (W - PAD * 2) // 2 - fm.horizontalAdvance(clock_text) // 2
        p.drawText(cx, PAD + BAR_H - 7, clock_text)

        # Status indicators (right)
        ix = W - PAD - 10
        for dot_color in [green, cyan, sub]:
            p.setBrush(dot_color)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(ix - 8, PAD + 8, 8, 8)
            ix -= 14

        # ── Terminal window ──────────────────────────────────────────────────
        TERM_Y     = PAD + BAR_H + 8
        TERM_H     = H - TERM_Y - PAD - 60  # leave room for notification + swatch grid
        TERM_W     = int((W - PAD * 2) * 0.62)
        self._rounded_rect(p, PAD, TERM_Y, TERM_W, TERM_H, 8, bg)

        # Titlebar dots
        p.setPen(Qt.PenStyle.NoPen)
        for i, dc in enumerate([red, orange, green]):
            p.setBrush(dc)
            p.drawEllipse(PAD + 8 + i * 14, TERM_Y + 6, 8, 8)

        # Prompt + command lines
        p.setFont(mono)
        ly = TERM_Y + 26
        lines = [
            (sub,    "❯ "),
            (cyan,   "ls"),
            (sub,    " -la ~/projects"),
            (None,   None),  # blank line
            (sub,    "total 24"),
            (None,   None),
            (green,  "drwxr-xr-x"),
            (text,   "  2 user user 4096 "),
            (orange, "Mar 15"),
            (text,   " ."),
            (None,   None),
            (green,  "drwxr-xr-x"),
            (text,   "  8 user user 4096 "),
            (orange, "Mar 14"),
            (text,   " .."),
            (None,   None),
            (blue,   "-rw-r--r--"),
            (text,   "  1 user user  248 "),
            (orange, "Mar 15"),
            (cyan,   " nord.json"),
        ]
        # Draw lines using segments
        segment_lines = [
            [(sub, "❯ "), (cyan, "ls"), (text, " -la")],
            [],
            [(text, "total 24")],
            [],
            [(green, "drwxr-xr-x"), (text, "  user  "), (orange, "Mar 15"), (text, "  .")],
            [(green, "drwxr-xr-x"), (text, "  user  "), (orange, "Mar 14"), (text, "  ..")],
            [(blue,  "-rw-r--r--"), (text, "  user  "), (orange, "Mar 15"), (cyan, "  nord.json")],
            [(blue,  "-rw-r--r--"), (text, "  user  "), (orange, "Mar 10"), (teal, "  catppuccin.json")],
            [(red,   "error: "), (text, "file not found")],
        ]
        p.setFont(mono)
        fm_mono = QFontMetrics(mono)
        for seg_line in segment_lines:
            if ly > TERM_Y + TERM_H - 8:
                break
            if not seg_line:
                ly += fm_mono.lineSpacing() - 2
                continue
            x = PAD + 10
            for color, txt in seg_line:
                if color is None or txt is None:
                    continue
                p.setPen(QPen(color))
                p.drawText(x, ly, txt)
                x += fm_mono.horizontalAdvance(txt)
            ly += fm_mono.lineSpacing()

        # ── Notification popup (right of terminal) ──────────────────────────
        NOTIF_X = PAD + TERM_W + 8
        NOTIF_W = W - PAD - NOTIF_X
        NOTIF_H = min(TERM_H, 90)
        self._rounded_rect(p, NOTIF_X, TERM_Y, NOTIF_W, NOTIF_H, 8, surface)

        p.setFont(sans)
        p.setPen(QPen(text))
        p.drawText(NOTIF_X + 10, TERM_Y + 18, "🎨 Theme Applied")

        p.setFont(small)
        p.setPen(QPen(sub))
        p.drawText(NOTIF_X + 10, TERM_Y + 34, "Switched to Nord")
        p.drawText(NOTIF_X + 10, TERM_Y + 48, "dark variant")

        # OK button
        btn_w, btn_h = 46, 22
        btn_x = NOTIF_X + NOTIF_W - btn_w - 8
        btn_y = TERM_Y + NOTIF_H - btn_h - 8
        self._rounded_rect(p, btn_x, btn_y, btn_w, btn_h, 5, cyan)
        p.setFont(small)
        p.setPen(QPen(bg))
        p.drawText(
            QRect(btn_x, btn_y, btn_w, btn_h),
            Qt.AlignmentFlag.AlignCenter, "OK"
        )

        # ── Color swatch grid (bottom) ────────────────────────────────────────
        role_order = [r for r, _ in COLOR_ROLE_LABELS]
        GRID_Y   = H - 52
        CELL_W   = (W - PAD * 2) // len(role_order)
        CELL_H   = 20
        LABEL_H  = 12

        p.setFont(QFont("Noto Sans", 6))
        for i, role in enumerate(role_order):
            hex_val = c.get(role, "#888888")
            color   = QColor(hex_val) if hex_val else QColor("#888888")
            cell_x  = PAD + i * CELL_W

            p.fillRect(cell_x, GRID_Y, CELL_W - 1, CELL_H, color)

            # Role label below swatch
            p.setPen(QPen(sub))
            fm_small = QFontMetrics(QFont("Noto Sans", 6))
            abbr = role[:3]
            tx = cell_x + (CELL_W - 1 - fm_small.horizontalAdvance(abbr)) // 2
            p.drawText(tx, GRID_Y + CELL_H + LABEL_H - 2, abbr)

    def _rounded_rect(self, p: QPainter, x: int, y: int,
                       w: int, h: int, r: int, color: QColor) -> None:
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(x, y, w, h, r, r)


class PreviewPanel(QWidget):
    """
    Right panel: live QPainter mockup + 'Preview System' button.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._mockup = _MockupWidget()
        layout.addWidget(self._mockup, 1)

        # ── Preview System button ─────────────────────────────────────────────
        btn_wrapper = QWidget()
        btn_wrapper.setFixedHeight(52)
        bl = QVBoxLayout(btn_wrapper)
        bl.setContentsMargins(12, 8, 12, 8)

        self._preview_sys_btn = QPushButton("Preview System")
        self._preview_sys_btn.setFixedHeight(34)
        self._preview_sys_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_sys_btn.clicked.connect(self._do_preview_system)
        bl.addWidget(self._preview_sys_btn)

        layout.addWidget(btn_wrapper)

        self._current_colors: dict = {}

    def update_colors(self, colors: dict) -> None:
        self._current_colors = colors
        self._mockup.update_colors(colors)

    def _do_preview_system(self) -> None:
        """Write _preview.json and call sauce switch _preview."""
        if not self._current_colors:
            return
        import json
        from ..config import PALETTES_DIR

        preview = {
            "_name": "_preview",
            "_mode": "dark",
            "_default_variant": "dark",
            "dark": self._current_colors,
        }
        preview_path = PALETTES_DIR / "_preview.json"
        try:
            PALETTES_DIR.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(json.dumps(preview, indent=2))
            switch_palette("_preview", reload=True)
        except Exception:
            pass
