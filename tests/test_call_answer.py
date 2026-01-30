import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from call_manager import CallManager


def test_answer_sends_at_and_starts_audio():
    cfg = MagicMock()
    bt = MagicMock()
    audio = MagicMock()
    cm = CallManager(cfg, bt_manager=bt, audio_manager=audio)
    cm.incoming("+123")
    assert cm.state == "incoming"
    cm.answer()
    # should have started sco/audio
    audio.start_sco.assert_called()
    # should have sent ATA
    bt.send_at.assert_called_with("ATA")
    assert cm.state == "active"
