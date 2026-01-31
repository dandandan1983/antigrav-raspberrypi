import logging
from configparser import ConfigParser
from typing import Optional

try:
    import pulsectl
except Exception:
    pulsectl = None


class AudioManager:
    """Audio manager integrating with PulseAudio via pulsectl.

    Provides methods to set HFP/HSP profiles on a BlueZ card and
    basic volume/profile controls. The implementation is defensive
    so it works even when PulseAudio is not present (stub mode).
    """

    def __init__(self, cfg: ConfigParser, logger: logging.Logger = None):
        self.cfg = cfg
        self.logger = logger or logging.getLogger("AudioManager")
        self.pulse: Optional["pulsectl.Pulse"] = None
        # persisted state file for simple state (volume)
        from pathlib import Path
        # allow configuring persistent state directory via config `misc.state_dir`
        try:
            state_dir = None
            if hasattr(self.cfg, "get"):
                state_dir = self.cfg.get("misc", "state_dir", fallback=None)
            if not state_dir:
                state_dir = "/var/lib/rpi-handsfree"
            self._state_file = Path(state_dir) / "state.json"
        except Exception:
            self._state_file = Path(__file__).resolve().parents[1] / "state.json"
        self.volume = 50
        self._load_state()

    def start(self):
        self.logger.info("AudioManager starting")
        if pulsectl is None:
            self.logger.info("pulsectl not available; running in stub mode")
            return
        try:
            self.pulse = pulsectl.Pulse("rpi-handsfree")
            self.logger.debug("Connected to PulseAudio server")
        except Exception:
            self.logger.exception("Failed to connect to PulseAudio")
            self.pulse = None

    def stop(self):
        self.logger.info("AudioManager stopping")
        if self.pulse:
            try:
                self.pulse.close()
            except Exception:
                self.logger.debug("Error closing pulsectl connection")

    def find_bluez_card(self):
        if not self.pulse:
            return None
        for card in self.pulse.card_list():
            try:
                if "bluez" in (card.name or ""):
                    return card
            except Exception:
                continue
        return None

    def set_hfp_profile(self, profile: str = "headset_head_unit") -> bool:
        """Set BlueZ card profile to HFP/HSP profile name.

        `profile` is typically `headset_head_unit` for HFP/HSP hands-free.
        Returns True on success.
        """
        card = self.find_bluez_card()
        if not card:
            self.logger.warning("No BlueZ card found to set profile")
            return False
        if not self.pulse:
            self.logger.warning("PulseAudio not available")
            return False
        try:
            # pulsectl exposes card_profile_set
            self.pulse.card_profile_set(card.index, profile)
            self.logger.info("Set card %s profile to %s", card.name, profile)
            return True
        except Exception:
            self.logger.exception("Failed to set card profile")
            return False

    def start_sco(self):
        """Hook called when a SCO/HFP call should start.

        This attempts to set the BlueZ card to the HFP/HSP profile and then
        route any active BlueZ `source-output` streams (phone SCO streams)
        onto the physical microphone source so the remote party hears the
        Pi microphone instead of a local monitor/loopback.
        """
        self.logger.debug("start_sco requested")
        ok = self.set_hfp_profile("headset_head_unit")

        # Ensure pulsectl connection
        if pulsectl is None:
            self.logger.debug("pulsectl not available, skipping SCO routing")
            return ok
        if not self.pulse:
            try:
                self.pulse = pulsectl.Pulse("rpi-handsfree")
            except Exception:
                self.logger.exception("Failed to connect to PulseAudio for SCO routing")
                return ok

        try:
            capture_cfg = None
            try:
                capture_cfg = self.cfg.get("audio", "capture_device", fallback=None)
            except Exception:
                capture_cfg = None

            # Find a sensible physical microphone source. Preference order:
            #  - explicit name from config (substring match)
            #  - PipeWire/ALSA source that mentions the codec/board (platform-soc_sound or Zero)
            mic = None
            for s in self.pulse.source_list():
                name = (s.name or "")
                if capture_cfg and capture_cfg != "default" and capture_cfg in name:
                    mic = s
                    break
                if "platform-soc_sound" in name or "Zero" in name or "alsa_input" in name:
                    mic = s
                    break

            if not mic:
                self.logger.warning("Physical mic source not found for SCO routing")
                return ok

            # Move all bluez-related source-outputs (SCO streams) to the physical mic
            for so in self.pulse.source_output_list():
                try:
                    proplist = getattr(so, "proplist", {}) or {}
                    is_bluez = bool(proplist.get("api.bluez5.address") or proplist.get("media.role") == "phone")
                    if not is_bluez:
                        continue
                    try:
                        self.pulse.source_output_move(so.index, mic.index)
                        self.logger.info("Moved source-output %s -> %s", so.index, mic.name)
                    except Exception:
                        self.logger.exception("Failed to move source-output %s", so.index)
                except Exception:
                    continue
        except Exception:
            self.logger.exception("Error while routing SCO source-outputs")

        return ok

    def stop_sco(self):
        self.logger.debug("stop_sco requested")
        # Optionally switch back to a2dp_sink or off; leaving as no-op for now
        return True

    def _load_state(self):
        try:
            import json
            if self._state_file.exists():
                with open(self._state_file, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    self.volume = int(s.get("volume", self.volume))
        except Exception:
            self.logger.debug("No previous state or failed to load state")

    def _save_state(self):
        try:
            import json
            with open(self._state_file, "w", encoding="utf-8") as f:
                json.dump({"volume": int(self.volume)}, f)
        except Exception:
            self.logger.exception("Failed to persist state")

    def set_volume(self, level: int):
        """Set absolute application-level volume (0-100) and persist it."""
        level = max(0, min(100, int(level)))
        self.volume = level
        self._save_state()
        if not self.pulse:
            self.logger.debug("set_volume stub: %s", level)
            return
        try:
            # Set volume on default sink (use first sink)
            sink_list = self.pulse.sink_list()
            if not sink_list:
                return
            sink = sink_list[0]
            # convert to pulsectl Volume format
            vol_val = level / 100.0
            self.pulse.volume_set_all_chans(sink, vol_val)
        except Exception:
            self.logger.exception("Failed to set volume")

    def volume_up(self, step: int = 5):
        self.set_volume(self.volume + step)

    def volume_down(self, step: int = 5):
        self.set_volume(self.volume - step)

