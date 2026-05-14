"""sauce.gui.window — MainWindow with three-pane QSplitter layout."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QLabel, QMainWindow, QSplitter, QStatusBar, QWidget,
)

from ..config import get_active, load_palette, parse_palette_spec, resolve_variant
from .color_editor import ColorEditorPanel
from .palette_list import PaletteListPanel
from .preview import PreviewPanel


class MainWindow(QMainWindow):
    """
    900×650 floating window.

    Left  (22%): PaletteListPanel  — palette list with swatch strips
    Center(48%): ColorEditorPanel  — 13-role color editor with undo/redo
    Right (30%): PreviewPanel      — live QPainter mockup
    """

    # Emitted after a palette is applied — carries the new variant colors dict
    # so app.py can re-apply the Qt stylesheet.
    theme_applied = Signal(dict)

    def __init__(self, initial_palette: str | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Sauce")
        self.resize(960, 660)
        self.setMinimumSize(700, 500)

        # ── Panels ──────────────────────────────────────────────────────────
        self.palette_list   = PaletteListPanel()
        self.color_editor   = ColorEditorPanel()
        self.preview_panel  = PreviewPanel()

        # ── Splitter ─────────────────────────────────────────────────────────
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.palette_list)
        self.splitter.addWidget(self.color_editor)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.setStretchFactor(0, 22)
        self.splitter.setStretchFactor(1, 48)
        self.splitter.setStretchFactor(2, 30)
        self.splitter.setHandleWidth(1)
        self.setCentralWidget(self.splitter)

        # ── Status bar ───────────────────────────────────────────────────────
        self._status = QStatusBar()
        self._status.setSizeGripEnabled(False)
        self.setStatusBar(self._status)
        self._status_label = QLabel("Ready")
        self._status.addWidget(self._status_label)

        # ── Menu bar ─────────────────────────────────────────────────────────
        self._build_menu()

        # ── Connect signals ──────────────────────────────────────────────────
        # Palette list → editor
        self.palette_list.palette_selected.connect(self._on_palette_selected)
        self.palette_list.new_requested.connect(self._on_new_palette)

        # Editor → preview (live color updates)
        self.color_editor.colors_changed.connect(self.preview_panel.update_colors)

        # Editor → status bar
        self.color_editor.status_message.connect(self._status_label.setText)

        # Editor applied a palette → refresh list + re-theme GUI
        self.color_editor.palette_applied.connect(self._on_palette_applied)
        self.color_editor.palette_saved.connect(self.palette_list.reload)

        # ── Initial load ─────────────────────────────────────────────────────
        target = initial_palette or self._active_stem()
        if target:
            self.palette_list.select_palette(target)
            self._load_palette(target)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        new_act = QAction("New Palette", self)
        new_act.setShortcut(QKeySequence("Ctrl+N"))
        new_act.triggered.connect(self._on_new_palette)
        file_menu.addAction(new_act)

        file_menu.addSeparator()

        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence("Ctrl+Q"))
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        edit_menu = self.menuBar().addMenu("Edit")

        undo_act = QAction("Undo", self)
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        undo_act.triggered.connect(self.color_editor.undo)
        edit_menu.addAction(undo_act)

        redo_act = QAction("Redo", self)
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        redo_act.triggered.connect(self.color_editor.redo)
        edit_menu.addAction(redo_act)

    @staticmethod
    def _active_stem() -> str | None:
        spec = get_active()
        if spec:
            name, _ = parse_palette_spec(spec)
            return name
        return None

    def _load_palette(self, stem: str) -> None:
        try:
            palette = load_palette(stem)
        except Exception as e:
            self._status_label.setText(f"Error loading {stem}: {e}")
            return
        self.color_editor.load_palette(stem, palette)
        # Seed preview with first variant's colors
        variants = [k for k in palette if not k.startswith("_")]
        if variants:
            self.preview_panel.update_colors(palette.get(variants[0], {}))

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_palette_selected(self, stem: str) -> None:
        self._load_palette(stem)

    def _on_new_palette(self) -> None:
        # Inherit colors from the currently loaded palette as a starting point
        self.color_editor.new_palette()

    def _on_palette_applied(self, stem: str, variant: str) -> None:
        self._status_label.setText(f"Applied: {stem}:{variant}")
        self.palette_list.reload()
        try:
            palette = load_palette(stem)
            colors  = palette.get(variant, {})
            self.theme_applied.emit(colors)
        except Exception:
            pass
