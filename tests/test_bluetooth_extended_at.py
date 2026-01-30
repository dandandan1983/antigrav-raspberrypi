import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bluetooth_manager import BluetoothManager


def test_extended_at_parsing():
    cfg = type("C", (), {"getboolean": lambda *a, **k: True})()
    bm = BluetoothManager(cfg)
    events = []

    def cb(path, ev):
        events.append(ev)

    bm.register_callback(cb)
    bm._handle_at_line('+CIEV: 2,1')
    bm._handle_at_line('+BTRH: 1')
    bm._handle_at_line('+CNUM: "+18005551212",129,2')
    bm._handle_at_line('+CLIP: "+123456789",129')

    assert any(e.get('event') == 'indicator' and e.get('indicator', {}).get('name') == 'callsetup' for e in events)
    assert any(e.get('event') == 'btrh' for e in events)
    assert any(e.get('event') == 'cnum' and e.get('number') == '+18005551212' for e in events)
    assert any(e.get('event') == 'clip' and e.get('number') == '+123456789' for e in events)
