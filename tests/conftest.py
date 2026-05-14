import json
import shutil
from pathlib import Path
import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Isolated sauce data dir with test fixtures. Patches module-level paths."""
    palettes  = tmp_path / "palettes"
    templates = tmp_path / "templates"
    generated = tmp_path / "generated"
    palettes.mkdir()
    templates.mkdir()
    generated.mkdir()

    shutil.copy(FIXTURES_DIR / "palettes" / "test.json", palettes / "test.json")
    shutil.copy(FIXTURES_DIR / "registry.toml", tmp_path / "registry.toml")

    import sauce.config as cfg
    monkeypatch.setattr(cfg, "SAUCE_DIR",     tmp_path)
    monkeypatch.setattr(cfg, "PALETTES_DIR",  palettes)
    monkeypatch.setattr(cfg, "TEMPLATES_DIR", templates)
    monkeypatch.setattr(cfg, "GENERATED_DIR", generated)
    monkeypatch.setattr(cfg, "REGISTRY_PATH", tmp_path / "registry.toml")
    monkeypatch.setattr(cfg, "ACTIVE_FILE",   tmp_path / "active")

    yield tmp_path
