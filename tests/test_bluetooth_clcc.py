import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluetooth_manager import BluetoothManager


def test_clcc_parsing_changes_call_state():
    cfg = type("C", (), {"getboolean": lambda *a, **k: True})()
    bm = BluetoothManager(cfg)
    events = []

    def cb(path, ev):
        events.append(ev)

    bm.register_callback(cb)
    # simulate CLCC incoming (status 4)
    bm._handle_at_line('+CLCC: 1,0,4,0,0,"+123456789",129')
    assert any(e.get("event") == "call_state" and e.get("state") == "incoming" for e in events)

    events.clear()
    # simulate CLCC active (status 0)
    bm._handle_at_line('+CLCC: 1,0,0,0,0,"+123456789",129')
    assert any(e.get("event") == "call_state" and e.get("state") == "active" for e in events)
