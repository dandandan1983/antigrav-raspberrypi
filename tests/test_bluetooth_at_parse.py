import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluetooth_manager import BluetoothManager


def test_at_parsing_calls_callbacks():
    cfg = type("C", (), {"getboolean": lambda *a, **k: True})()
    bm = BluetoothManager(cfg)
    events = []

    def cb(path, ev):
        events.append(ev)

    bm.register_callback(cb)
    # call internal handler directly with sample lines
    bm._handle_at_line("RING")
    bm._handle_at_line("+VGS: 10")
    bm._handle_at_line("+CIEV: 1,1")
    assert any(e.get("event") == "ring" for e in events)
    assert any(e.get("event") == "remote_volume" for e in events)
    assert any(e.get("event") == "indicator" for e in events)
