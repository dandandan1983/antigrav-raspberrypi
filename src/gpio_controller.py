import logging
from configparser import ConfigParser
from threading import Event, Thread
import time

try:
    import RPi.GPIO as GPIO
except Exception:
    GPIO = None


class GPIOController:
    """GPIO controller with button handling and LED patterns.

    Uses `RPi.GPIO` when available; otherwise runs in stub mode.
    Callers may register callbacks on button events.
    """

    def __init__(self, cfg: ConfigParser, logger: logging.Logger = None):
        self.cfg = cfg
        self.logger = logger or logging.getLogger("GPIOController")
        self._available = GPIO is not None
        self._btn_pins = {}
        self._led_pins = {}
        self._blink_thread: Thread | None = None
        self._blink_stop = Event()
        self._pattern = "idle"
        self._callbacks = {}

    def start(self):
        if not self._available:
            self.logger.info("GPIO not available; running stub mode")
            return
        self.logger.info("GPIOController initializing pins")
        try:
            GPIO.setmode(GPIO.BCM)
            # Load pin numbers from config
            try:
                self._btn_pins = {
                    "answer": int(self.cfg.get("gpio", "button_answer", fallback=17)),
                    "reject": int(self.cfg.get("gpio", "button_reject", fallback=27)),
                    "vol_up": int(self.cfg.get("gpio", "button_vol_up", fallback=22)),
                    "vol_down": int(self.cfg.get("gpio", "button_vol_down", fallback=23)),
                }
                self._led_pins = {
                    "status": int(self.cfg.get("gpio", "led_status", fallback=24)),
                    "call": int(self.cfg.get("gpio", "led_call", fallback=25)),
                }
            except Exception:
                self.logger.exception("Invalid GPIO configuration; using defaults")

            # Configure buttons
            for name, pin in self._btn_pins.items():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                # Callback with debounce via bouncetime
                GPIO.add_event_detect(pin, GPIO.FALLING, callback=self._make_button_handler(name), bouncetime=250)

            # Configure LEDs as outputs and turn off
            for pin in self._led_pins.values():
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)

            # Start blink thread
            self._blink_stop.clear()
            self._blink_thread = Thread(target=self._blink_loop, daemon=True)
            self._blink_thread.start()
        except Exception:
            self.logger.exception("Failed to initialize GPIO")

    def stop(self):
        self.logger.info("Stopping GPIOController")
        self._blink_stop.set()
        if self._blink_thread:
            self._blink_thread.join(timeout=1.0)
        if self._available:
            try:
                GPIO.cleanup()
            except Exception:
                pass

    def _make_button_handler(self, name: str):
        def handler(channel):
            self.logger.info("Button %s pressed (pin=%s)", name, channel)
            cb = self._callbacks.get(name)
            if cb:
                try:
                    cb()
                except Exception:
                    self.logger.exception("Button callback error for %s", name)

        return handler

    def on_button(self, name: str, callback):
        """Register a callback for a button name: `answer`, `reject`, `vol_up`, `vol_down`."""
        self._callbacks[name] = callback

    def set_pattern(self, pattern: str):
        """Set LED pattern: 'idle', 'connected', 'incoming', 'active'."""
        self._pattern = pattern

    def _blink_loop(self):
        # Simple patterns implementation
        while not self._blink_stop.is_set():
            try:
                if self._pattern == "idle":
                    self._set_led(self._led_pins.get("status"), False)
                    time.sleep(1.0)
                elif self._pattern == "connected":
                    self._set_led(self._led_pins.get("status"), True)
                    time.sleep(1.0)
                elif self._pattern == "incoming":
                    self._pulse_led(self._led_pins.get("call"), 0.2, 0.2, 3)
                elif self._pattern == "active":
                    self._pulse_led(self._led_pins.get("call"), 0.5, 0.5, 1)
                else:
                    time.sleep(1.0)
            except Exception:
                self.logger.exception("Error in blink loop")

    def _set_led(self, pin: int | None, on: bool):
        if not self._available or pin is None:
            return
        try:
            GPIO.output(pin, GPIO.HIGH if on else GPIO.LOW)
        except Exception:
            pass

    def _pulse_led(self, pin: int | None, on_dur: float, off_dur: float, repeats: int):
        if not self._available or pin is None:
            time.sleep(on_dur + off_dur)
            return
        for _ in range(repeats):
            if self._blink_stop.is_set():
                break
            self._set_led(pin, True)
            time.sleep(on_dur)
            self._set_led(pin, False)
            time.sleep(off_dur)

