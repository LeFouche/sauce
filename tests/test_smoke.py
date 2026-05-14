from sauce.config import list_palettes, get_active


def test_list_palettes_returns_test_palette(data_dir):
    palettes = list_palettes()
    assert "test" in palettes


def test_get_active_returns_none_when_no_active_file(data_dir):
    assert get_active() is None


def test_get_active_reads_active_file(data_dir):
    (data_dir / "active").write_text("test:dark")
    assert get_active() == "test:dark"
