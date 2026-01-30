from pathlib import Path
import sys

# Make src available for imports during tests
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import load_config


def test_load_config_exists():
    cfg = load_config(ROOT / "config.ini")
    assert cfg is not None
    assert cfg.has_section("bluetooth")
