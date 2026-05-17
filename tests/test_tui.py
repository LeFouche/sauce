import asyncio
import pytest


def _run(coro):
    """Run an async coroutine in a new event loop."""
    return asyncio.run(coro)


def test_tui_composes_without_error(data_dir):
    from sauce.tui import SauceApp
    from textual.widgets import ListView

    async def run():
        async with SauceApp().run_test() as pilot:
            assert pilot.app.query_one("#palette_list")
            assert pilot.app.query_one("#editor")

    _run(run())


def test_tui_palette_list_populated(data_dir):
    from sauce.tui import SauceApp
    from textual.widgets import ListView

    async def run():
        async with SauceApp().run_test() as pilot:
            lv = pilot.app.query_one("#palette_list", ListView)
            assert lv.children

    _run(run())


def test_tui_select_palette_populates_editor(data_dir):
    """Pressing down to select the first palette should populate the editor panel."""
    from sauce.tui import SauceApp
    from textual.containers import ScrollableContainer

    async def run():
        async with SauceApp().run_test() as pilot:
            # Focus the list, move to the first item, then confirm selection
            lv = pilot.app.query_one("#palette_list")
            lv.focus()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()

            editor = pilot.app.query_one("#editor", ScrollableContainer)
            # After selecting a palette, the editor should have child widgets (swatches/labels)
            assert len(editor.children) > 0

    _run(run())
