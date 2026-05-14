"""sauce.gui.color_editor — Center panel: palette metadata + 13-role color editor + undo/redo."""

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy,
    QTabWidget, QVBoxLayout, QWidget,
)

from ..config import (
    COLOR_ROLE_GROUPS, COLOR_ROLE_LABELS, PALETTES_DIR,
    get_active, load_palette, palette_variants, parse_palette_spec,
    resolve_variant,
)
from ..switch import switch_palette
from .color_row import ColorRow

# --------------------------------------------------------------------------- #
#  Undo command
# --------------------------------------------------------------------------- #

class _ColorChangeCmd(QUndoCommand):
    def __init__(self, editor: "ColorEditorPanel", variant: str, role: str,
                 old_hex: str, new_hex: str) -> None:
        super().__init__(f"Change {role}")
        self._editor   = editor
        self._variant  = variant
        self._role     = role
        self._old      = old_hex
        self._new      = new_hex

    def undo(self) -> None:
        self._editor._set_role_silent(self._variant, self._role, self._old)

    def redo(self) -> None:
        self._editor._set_role_silent(self._variant, self._role, self._new)


# --------------------------------------------------------------------------- #
#  Section header
# --------------------------------------------------------------------------- #

class _SectionHeader(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 4)
        layout.setSpacing(8)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            "font-size: 10px; font-weight: 700; letter-spacing: 0.1em; color: #888;"
        )
        layout.addWidget(lbl)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        layout.addWidget(line)


# --------------------------------------------------------------------------- #
#  Variant tab body
# --------------------------------------------------------------------------- #

class _VariantBody(QWidget):
    """Scrollable body for one variant: all color role groups."""

    colors_changed = Signal(dict)  # full variant color dict

    def __init__(self, role_labels: list[tuple[str, str]],
                 groups: list[tuple[str, list[str]]]) -> None:
        super().__init__()
        self._rows: dict[str, ColorRow] = {}
        self._colors: dict[str, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 16)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        label_map = dict(role_labels)

        for group_name, roles in groups:
            layout.addWidget(_SectionHeader(group_name))
            for role in roles:
                label = label_map.get(role, role)
                row   = ColorRow(role, label)
                row.color_changed.connect(self._on_color_changed)
                self._rows[role] = row
                layout.addWidget(row)

        layout.addStretch()

    def load_colors(self, colors: dict) -> None:
        """Populate rows from a variant color dict."""
        self._colors = dict(colors)
        for role, row in self._rows.items():
            hex_val = colors.get(role, "#888888")
            row.set_color(hex_val)

    def get_colors(self) -> dict:
        return dict(self._colors)

    def set_role(self, role: str, hex_color: str) -> None:
        """Set a single role (used by undo/redo) — does not emit."""
        self._colors[role] = hex_color
        if role in self._rows:
            self._rows[role].set_color(hex_color)
        self.colors_changed.emit(self.get_colors())

    def _on_color_changed(self, role: str, hex_color: str) -> None:
        self._colors[role] = hex_color
        self.colors_changed.emit(self.get_colors())


# --------------------------------------------------------------------------- #
#  Color editor panel
# --------------------------------------------------------------------------- #

class ColorEditorPanel(QWidget):
    """
    Center panel with:
      - Name / filename / mode header
      - QTabWidget — one tab per variant
      - Action bar: Preview | Cancel Preview | Save ▾ | Save & Apply
    """

    colors_changed  = Signal(dict)    # for live preview
    palette_applied = Signal(str, str)  # (stem, variant) after apply
    palette_saved   = Signal()          # after write to disk
    status_message  = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._stem: str | None         = None
        self._palette: dict            = {}
        self._undo_stack               = QUndoStack(self)
        self._preview_active           = False
        self._pre_preview_spec: str | None = None

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)
        hl.setSpacing(10)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Palette name")
        self._name_edit.setFixedHeight(32)

        self._file_edit = QLineEdit()
        self._file_edit.setPlaceholderText("filename")
        self._file_edit.setFixedWidth(120)
        self._file_edit.setFixedHeight(32)

        self._mode_btn = QPushButton("dark")
        self._mode_btn.setFixedSize(52, 28)
        self._mode_btn.setCheckable(True)
        self._mode_btn.clicked.connect(self._toggle_mode)

        hl.addWidget(QLabel("Name:"))
        hl.addWidget(self._name_edit, 1)
        hl.addWidget(QLabel("File:"))
        hl.addWidget(self._file_edit)
        hl.addWidget(self._mode_btn)
        main_layout.addWidget(header)

        # ── Separator ────────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        main_layout.addWidget(sep)

        # ── Tab widget (one tab per variant) ─────────────────────────────────
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._bodies: dict[str, _VariantBody] = {}
        main_layout.addWidget(self._tabs, 1)

        # ── Action bar ───────────────────────────────────────────────────────
        bar = QWidget()
        bar.setFixedHeight(52)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 8, 12, 8)
        bl.setSpacing(8)

        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setFixedHeight(34)
        self._preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_btn.clicked.connect(self._do_preview)

        self._cancel_btn = QPushButton("Cancel Preview")
        self._cancel_btn.setFixedHeight(34)
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._do_cancel_preview)

        self._save_btn = QPushButton("Save")
        self._save_btn.setFixedHeight(34)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._do_save)

        self._apply_btn = QPushButton("Save & Apply")
        self._apply_btn.setProperty("class", "accent")
        self._apply_btn.setFixedHeight(34)
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.clicked.connect(self._do_save_and_apply)

        bl.addWidget(self._preview_btn)
        bl.addWidget(self._cancel_btn)
        bl.addStretch()
        bl.addWidget(self._save_btn)
        bl.addWidget(self._apply_btn)
        main_layout.addWidget(bar)

    # ── Public interface ─────────────────────────────────────────────────────

    def load_palette(self, stem: str, palette: dict) -> None:
        """Load a palette into the editor."""
        self._stem    = stem
        self._palette = palette
        self._undo_stack.clear()

        self._name_edit.setText(palette.get("_name", stem))
        self._file_edit.setText(stem)

        # Populate variant tabs
        self._tabs.blockSignals(True)
        self._tabs.clear()
        self._bodies.clear()

        variants = palette_variants(palette)
        active_spec   = get_active()
        active_variant = None
        if active_spec:
            aname, ahint = parse_palette_spec(active_spec)
            if aname == stem:
                active_variant = resolve_variant(palette, ahint)

        for v in variants:
            body = _VariantBody(COLOR_ROLE_LABELS, COLOR_ROLE_GROUPS)
            body.load_colors(palette.get(v, {}))
            body.colors_changed.connect(self.colors_changed)
            self._bodies[v] = body

            scroll = QScrollArea()
            scroll.setWidget(body)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._tabs.addTab(scroll, v)

        # Activate the currently active variant tab
        if active_variant and active_variant in self._bodies:
            idx = list(self._bodies.keys()).index(active_variant)
            self._tabs.setCurrentIndex(idx)

        # Mode button
        mode = palette.get("_mode", "dark")
        self._mode_btn.setText(mode)
        self._mode_btn.setChecked(mode == "light")

        self._tabs.blockSignals(False)

        # Emit initial colors for preview
        current_variant = list(self._bodies.keys())[self._tabs.currentIndex()] \
            if self._bodies else None
        if current_variant:
            self.colors_changed.emit(self._bodies[current_variant].get_colors())

    def new_palette(self, base_palette: dict | None = None) -> None:
        """Open a blank (or inherited) palette for editing."""
        stub: dict = {"_name": "New Palette", "_mode": "dark", "_default_variant": "dark",
                      "dark": {}}
        if base_palette:
            # Inherit colors from first variant of base
            variants = palette_variants(base_palette)
            if variants:
                stub["dark"] = dict(base_palette.get(variants[0], {}))
        self.load_palette("new-palette", stub)

    def undo(self) -> None:
        self._undo_stack.undo()

    def redo(self) -> None:
        self._undo_stack.redo()

    # ── Undo/redo helper called by _ColorChangeCmd ────────────────────────────

    def _set_role_silent(self, variant: str, role: str, hex_color: str) -> None:
        if variant in self._bodies:
            self._bodies[variant].set_role(role, hex_color)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _current_variant(self) -> str | None:
        idx = self._tabs.currentIndex()
        keys = list(self._bodies.keys())
        return keys[idx] if 0 <= idx < len(keys) else None

    def _toggle_mode(self) -> None:
        mode = "light" if self._mode_btn.isChecked() else "dark"
        self._mode_btn.setText(mode)

    def _build_palette_json(self) -> dict:
        """Assemble a fresh palette dict from editor state."""
        pal: dict = {}
        name = self._name_edit.text().strip() or self._file_edit.text().strip() or "Unnamed"
        pal["_name"]            = name
        pal["_mode"]            = "light" if self._mode_btn.isChecked() else "dark"
        pal["_default_variant"] = list(self._bodies.keys())[0] if self._bodies else "dark"
        # Preserve metadata from original palette
        if self._palette:
            for mk in ("_author", "_qs_name", "_vscodium_theme", "_spicetify_community"):
                if mk in self._palette:
                    pal[mk] = self._palette[mk]
        for variant, body in self._bodies.items():
            pal[variant] = body.get_colors()
        return pal

    def _write_palette(self, stem: str) -> bool:
        """Write palette JSON to disk. Returns True on success."""
        pal_json = self._build_palette_json()
        dest = PALETTES_DIR / f"{stem}.json"
        try:
            PALETTES_DIR.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(pal_json, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            QMessageBox.critical(self, "Save error", str(e))
            return False

    # ── Actions ──────────────────────────────────────────────────────────────

    def _do_preview(self) -> None:
        if not self._stem:
            return
        self._pre_preview_spec = get_active()
        variant = self._current_variant() or "dark"
        pal_json = self._build_palette_json()
        preview_path = PALETTES_DIR / "_preview.json"
        try:
            PALETTES_DIR.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(json.dumps(pal_json, indent=2))
        except Exception as e:
            self.status_message.emit(f"Preview error: {e}")
            return

        if switch_palette("_preview", reload=True):
            self._preview_active = True
            self._cancel_btn.setEnabled(True)
            self.status_message.emit("Preview active — editing in live")
        else:
            self.status_message.emit("Preview failed")

    def _do_cancel_preview(self) -> None:
        if self._pre_preview_spec:
            switch_palette(self._pre_preview_spec, reload=True)
        self._preview_active = False
        self._cancel_btn.setEnabled(False)
        self.status_message.emit("Preview cancelled")

    def _do_save(self) -> None:
        stem = self._file_edit.text().strip() or "unnamed"
        if self._write_palette(stem):
            self._stem = stem
            self.palette_saved.emit()
            self.status_message.emit(f"Saved: {stem}.json")

    def _do_save_and_apply(self) -> None:
        stem = self._file_edit.text().strip() or "unnamed"
        if not self._write_palette(stem):
            return
        self._stem = stem
        variant = self._current_variant() or "dark"
        spec    = f"{stem}:{variant}"
        if switch_palette(spec, reload=True):
            self._preview_active = False
            self._cancel_btn.setEnabled(False)
            self.palette_applied.emit(stem, variant)
            self.status_message.emit(f"Applied: {stem}:{variant}")
        else:
            self.status_message.emit(f"Apply failed for {spec}")
