import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audio_manager import AudioManager


class DummyCfg:
    def get(self, *args, **kwargs):
        return None


def test_audio_manager_stub():
    cfg = DummyCfg()
    am = AudioManager(cfg)
    # start should not raise even if pulsectl absent
    am.start()
    assert am.start_sco() in (True, False)
