import asyncio
import pytest


def test_tui_composes_without_error(data_dir):
    from sauce.tui import SauceApp
    from textual.widgets import ListView

    async def run():
        async with SauceApp().run_test() as pilot:
            assert pilot.app.query_one("#palette_list")
            assert pilot.app.query_one("#editor")

    asyncio.run(run())


def test_tui_palette_list_populated(data_dir):
    from sauce.tui import SauceApp
    from textual.widgets import ListView

    async def run():
        async with SauceApp().run_test() as pilot:
            lv = pilot.app.query_one("#palette_list", ListView)
            assert lv.children

    asyncio.run(run())
