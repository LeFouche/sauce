"""sauce.tui — Textual TUI palette browser and editor."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from .config import (
    COLOR_ROLE_LABELS,
    get_active,
    list_palettes,
    load_palette,
    palette_variants,
    parse_palette_spec,
)
from .switch import switch_palette


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contrast_fg(hex_color: str) -> str:
    """Return '#000000' or '#ffffff' for readable text on hex_color background."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#000000" if luminance > 0.179 else "#ffffff"


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------

class PaletteItem(ListItem):
    """A row in the palette list showing name and active marker."""

    DEFAULT_CSS = """
    PaletteItem {
        padding: 0 1;
    }
    PaletteItem.active Label {
        color: $success;
        text-style: bold;
    }
    """

    def __init__(self, palette_name: str, *, active: bool = False) -> None:
        super().__init__(id=f"pal_{palette_name}")
        self._palette_name = palette_name
        self._active = active

    def compose(self) -> ComposeResult:
        marker = " ←" if self._active else ""
        yield Label(f"{self._palette_name}{marker}")

    def on_mount(self) -> None:
        if self._active:
            self.add_class("active")

    @property
    def palette_name(self) -> str:
        return self._palette_name


class ColorSwatch(Static):
    """One color role displayed as a colored block with its hex value."""

    DEFAULT_CSS = """
    ColorSwatch {
        height: 3;
        padding: 1 2;
        margin: 0 1 1 1;
        content-align: left middle;
    }
    """

    def __init__(self, role: str, label: str, hex_color: str) -> None:
        fg = _contrast_fg(hex_color)
        content = f"[bold]{label}[/bold]  {hex_color}"
        super().__init__(content)
        self.styles.background = hex_color
        self.styles.color = fg


# ---------------------------------------------------------------------------
# Modal screens
# ---------------------------------------------------------------------------

class _HelpScreen(ModalScreen):
    """Keyboard shortcuts reference."""

    DEFAULT_CSS = """
    _HelpScreen {
        align: center middle;
    }
    _HelpScreen > Container {
        width: 60;
        height: auto;
        padding: 2 4;
        border: round $primary;
        background: $surface;
    }
    """

    BINDINGS = [Binding("escape,q,?", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("[bold]Keyboard shortcuts[/bold]\n")
            yield Static(
                "  [bold]Enter[/bold]   Apply selected palette\n"
                "  [bold]e[/bold]       Edit selected palette\n"
                "  [bold]n[/bold]       New palette\n"
                "  [bold]d[/bold]       Delete selected palette\n"
                "  [bold]q[/bold]       Quit\n"
                "  [bold]?[/bold]       Show this help\n"
            )
            yield Button("Close", variant="primary", id="help_close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help_close":
            self.dismiss()


class _ConfirmScreen(ModalScreen[bool]):
    """Yes/no confirmation dialog."""

    DEFAULT_CSS = """
    _ConfirmScreen {
        align: center middle;
    }
    _ConfirmScreen > Container {
        width: 50;
        height: auto;
        padding: 2 4;
        border: round $warning;
        background: $surface;
    }
    _ConfirmScreen Horizontal {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    _ConfirmScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [Binding("escape", "dismiss_false", "Cancel")]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self._message)
            with Horizontal():
                yield Button("Yes", variant="error", id="confirm_yes")
                yield Button("No", variant="primary", id="confirm_no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm_yes")

    def action_dismiss_false(self) -> None:
        self.dismiss(False)


class _EditScreen(ModalScreen):
    """Simple form to create or edit a palette (name + JSON path hint)."""

    DEFAULT_CSS = """
    _EditScreen {
        align: center middle;
    }
    _EditScreen > Container {
        width: 70;
        height: auto;
        padding: 2 4;
        border: round $primary;
        background: $surface;
    }
    _EditScreen Input {
        margin-bottom: 1;
    }
    _EditScreen Horizontal {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    _EditScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, palette_name: str = "") -> None:
        super().__init__()
        self._palette_name = palette_name
        self._is_new = not palette_name

    def compose(self) -> ComposeResult:
        title = "New Palette" if self._is_new else f"Edit: {self._palette_name}"
        with Container():
            yield Label(f"[bold]{title}[/bold]\n")
            yield Label("Palette name:")
            yield Input(
                value=self._palette_name,
                placeholder="e.g. nord",
                id="edit_name",
            )
            yield Label("Palette file path (JSON):")
            yield Input(
                placeholder="Leave blank to create empty palette",
                id="edit_path",
            )
            with Horizontal():
                yield Button("Save", variant="success", id="edit_save")
                yield Button("Cancel", variant="default", id="edit_cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "edit_cancel":
            self.dismiss(None)
        elif event.button.id == "edit_save":
            name_input = self.query_one("#edit_name", Input)
            self.dismiss(name_input.value.strip() or None)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class SauceApp(App):
    """Sauce TUI — interactive palette browser and editor."""

    TITLE = "sauce — palette manager"
    SUB_TITLE = "Press ? for help"

    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 30;
        height: 100%;
        border-right: solid $primary;
        layout: vertical;
    }

    #sidebar_title {
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 1 2;
    }

    #palette_list {
        height: 1fr;
    }

    #sidebar_buttons {
        height: auto;
        padding: 1;
    }

    #sidebar_buttons Button {
        width: 100%;
        margin-bottom: 1;
    }

    #editor_panel {
        width: 1fr;
        height: 100%;
        layout: vertical;
    }

    #editor_header {
        height: 3;
        content-align: left middle;
        padding: 1 2;
        background: $surface;
        border-bottom: solid $primary;
    }

    #editor {
        height: 1fr;
        padding: 1;
    }

    #status_bar {
        height: 3;
        content-align: left middle;
        padding: 0 2;
        background: $surface;
        border-top: solid $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "edit", "Edit"),
        Binding("n", "new", "New"),
        Binding("enter", "apply", "Apply", show=True),
        Binding("d", "delete", "Delete"),
        Binding("question_mark", "help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active_spec: str | None = get_active()
        self._selected_palette: str | None = None

    # ------------------------------------------------------------------
    # Compose
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Container(id="sidebar"):
            yield Static("Palettes", id="sidebar_title")
            yield ListView(id="palette_list")
            with Vertical(id="sidebar_buttons"):
                yield Button("+ New", variant="success", id="btn_new")

        with Container(id="editor_panel"):
            yield Static("Select a palette to preview", id="editor_header")
            yield ScrollableContainer(id="editor")
            yield Static("", id="status_bar")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def on_mount(self) -> None:
        await self._populate_palette_list()

    async def _populate_palette_list(self) -> None:
        lv = self.query_one("#palette_list", ListView)
        await lv.clear()

        active_name: str | None = None
        if self._active_spec:
            active_name, _ = parse_palette_spec(self._active_spec)

        for name in list_palettes():
            is_active = name == active_name
            await lv.append(PaletteItem(name, active=is_active))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, PaletteItem):
            self._selected_palette = event.item.palette_name
            await self._show_palette(event.item.palette_name)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_new":
            await self.action_new()

    # ------------------------------------------------------------------
    # Palette preview
    # ------------------------------------------------------------------

    async def _show_palette(self, name: str) -> None:
        header = self.query_one("#editor_header", Static)
        editor = self.query_one("#editor", ScrollableContainer)
        await editor.remove_children()

        try:
            palette = load_palette(name)
        except FileNotFoundError:
            header.update(f"[red]Palette not found:[/red] {name}")
            return

        variants = palette_variants(palette)
        header.update(f"[bold]{name}[/bold]   variants: {', '.join(variants)}")

        # Show swatches for each variant
        for variant in variants:
            variant_data = palette.get(variant, {})
            await editor.mount(Static(f"\n[bold underline]{variant}[/bold underline]"))
            for role, label in COLOR_ROLE_LABELS:
                hex_color = variant_data.get(role)
                if hex_color:
                    await editor.mount(ColorSwatch(role, label, hex_color))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_apply(self) -> None:
        if not self._selected_palette:
            self._set_status("[yellow]No palette selected.[/yellow]")
            return
        try:
            switch_palette(self._selected_palette)
            self._active_spec = f"{self._selected_palette}"
            await self._populate_palette_list()
            self._set_status(
                f"[green]Applied:[/green] {self._selected_palette}"
            )
        except Exception as exc:
            self._set_status(f"[red]Error applying palette:[/red] {exc}")

    async def action_edit(self) -> None:
        name = self._selected_palette
        if not name:
            self._set_status("[yellow]No palette selected to edit.[/yellow]")
            return

        result = await self.push_screen_wait(_EditScreen(palette_name=name))
        if result:
            self._set_status(f"[green]Saved:[/green] {result}")

    async def action_new(self) -> None:
        result = await self.push_screen_wait(_EditScreen())
        if result:
            self._set_status(
                f"[green]New palette stub:[/green] {result} "
                "(create the JSON file manually)"
            )
            await self._populate_palette_list()

    async def action_delete(self) -> None:
        name = self._selected_palette
        if not name:
            self._set_status("[yellow]No palette selected to delete.[/yellow]")
            return

        confirmed = await self.push_screen_wait(
            _ConfirmScreen(f"Delete palette [bold]{name}[/bold]?")
        )
        if confirmed:
            from .config import PALETTES_DIR
            path = PALETTES_DIR / f"{name}.json"
            if path.exists():
                path.unlink()
                self._selected_palette = None
                await self._populate_palette_list()
                editor = self.query_one("#editor", ScrollableContainer)
                await editor.remove_children()
                self.query_one("#editor_header", Static).update(
                    "Select a palette to preview"
                )
                self._set_status(f"[red]Deleted:[/red] {name}")
            else:
                self._set_status(f"[red]File not found:[/red] {path}")

    async def action_help(self) -> None:
        await self.push_screen(_HelpScreen())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self.query_one("#status_bar", Static).update(message)


# ---------------------------------------------------------------------------
# Module-level entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Launch the Sauce TUI."""
    SauceApp().run()
