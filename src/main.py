import logging
import signal
import sys
import time
from config import load_config
from logger_setup import configure_logging
from bluetooth_manager import BluetoothManager
from audio_manager import AudioManager
from call_manager import CallManager
from gpio_controller import GPIOController


class MainApp:
    def __init__(self, config_path: str = None):
        self.cfg = load_config(config_path)
        configure_logging(self.cfg)
        self.logger = logging.getLogger("MainApp")

        # Initialize components
        self.bt = BluetoothManager(self.cfg, logger=logging.getLogger("BluetoothManager"))
        self.audio = AudioManager(self.cfg, logger=logging.getLogger("AudioManager"))
        self.call = CallManager(self.cfg, bt_manager=self.bt, audio_manager=self.audio,
                                logger=logging.getLogger("CallManager"))
        self.gpio = GPIOController(self.cfg, logger=logging.getLogger("GPIOController"))
        self._running = False

    def start(self):
        self.logger.info("Starting RPi Hands-Free application")
        self._running = True
        self.bt.start()
        self.audio.start()
        self.gpio.start()

        # Wire GPIO buttons to call manager actions
        try:
            self.gpio.on_button("answer", lambda: self._on_answer())
            self.gpio.on_button("reject", lambda: self._on_reject())
            self.gpio.on_button("vol_up", lambda: self._on_vol_up())
            self.gpio.on_button("vol_down", lambda: self._on_vol_down())
        except Exception:
            self.logger.exception("Failed to register GPIO callbacks")
        # Register Bluetooth event callbacks (RFCOMM AT events)
        try:
            self.bt.register_callback(self._on_bt_event)
        except Exception:
            self.logger.exception("Failed to register BT callbacks")

        # Simple run loop — replace with event-driven loop in next iterations
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received, shutting down")
        finally:
            self.stop()

    def stop(self):
        if not self._running:
            return
        self.logger.info("Stopping RPi Hands-Free application")
        self._running = False
        try:
            self.gpio.stop()
            self.audio.stop()
            self.bt.stop()
        except Exception:
            self.logger.exception("Error during shutdown")

    # GPIO action handlers
    def _on_answer(self):
        try:
            if self.call.state == "incoming":
                self.call.answer()
                self.gpio.set_pattern("active")
            elif self.call.state == "active":
                self.call.hangup()
                self.gpio.set_pattern("connected")
        except Exception:
            self.logger.exception("Error handling answer button")

    def _on_reject(self):
        try:
            if self.call.state == "incoming":
                self.call.hangup()
                self.gpio.set_pattern("connected")
        except Exception:
            self.logger.exception("Error handling reject button")

    def _on_vol_up(self):
        try:
            self.audio.volume_up()
        except Exception:
            self.logger.exception("Error handling vol_up")

    def _on_vol_down(self):
        try:
            self.audio.volume_down()
        except Exception:
            self.logger.exception("Error handling vol_down")

    def _on_bt_event(self, path, ev: dict):
        try:
            if not ev:
                return
            event = ev.get("event")
            if event == "ring":
                # incoming call
                self.call.incoming(None)
                self.gpio.set_pattern("incoming")
            elif event == "ok":
                self.logger.debug("BT AT OK received")
            elif event == "indicator":
                self.logger.debug("BT indicator: %s", ev.get("value"))
            elif event == "remote_volume":
                # parse +VGS or +VGM to extract numeric value if present
                try:
                    import re
                    m = re.search(r"(\d+)", ev.get("value", ""))
                    if m:
                        vol = int(m.group(1))
                        # HFP volume is 0-15 typical — map to 0-100
                        vol_pct = int(vol / 15.0 * 100)
                        self.audio.set_volume(vol_pct)
                except Exception:
                    self.logger.exception("Failed to parse remote volume")
            else:
                self.logger.debug("Unhandled BT event: %s", ev)
        except Exception:
            self.logger.exception("Error in BT event handler")


def main():
    app = MainApp()

    def _sigterm(signum, frame):
        app.logger.info("Signal %s received, shutting down", signum)
        app.stop()

    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT, _sigterm)

    app.start()


if __name__ == "__main__":
    main()
