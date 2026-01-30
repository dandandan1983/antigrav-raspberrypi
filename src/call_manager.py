import logging
from configparser import ConfigParser


class CallManager:
    """Manage call state and translate requests into Bluetooth AT commands.

    This is a high-level stub. It will coordinate with BluetoothManager
    and AudioManager in later iterations.
    """

    def __init__(self, cfg: ConfigParser, bt_manager=None, audio_manager=None, logger: logging.Logger = None):
        self.cfg = cfg
        self.bt = bt_manager
        self.audio = audio_manager
        self.logger = logger or logging.getLogger("CallManager")
        self.state = "idle"

    def incoming(self, number: str = None):
        self.logger.info("Incoming call from %s", number)
        self.state = "incoming"
        # ensure GPIO/LEDs may be updated by caller; audio not started until answer

    def answer(self):
        self.logger.info("Answering call")
        # Start SCO/audio routing
        try:
            if self.audio:
                self.audio.start_sco()
        except Exception:
            self.logger.exception("Audio start failed")
        # Send ATA to remote device
        if self.bt:
            try:
                self.bt.send_at("ATA")
            except Exception:
                self.logger.exception("Failed to send ATA")
        self.state = "active"

    def hangup(self):
        self.logger.info("Hanging up")
        # Stop SCO/audio routing
        try:
            if self.audio:
                self.audio.stop_sco()
        except Exception:
            self.logger.exception("Audio stop failed")
        if self.bt:
            try:
                self.bt.send_at("AT+CHUP")
            except Exception:
                self.logger.exception("Failed to send AT+CHUP")
        self.state = "idle"
    
