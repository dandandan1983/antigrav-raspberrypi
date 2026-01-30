import logging
from configparser import ConfigParser
from typing import Callable, Dict, List, Optional
import threading
import time

try:
    from pydbus import SystemBus
    from gi.repository import GLib
except Exception:
    SystemBus = None
    GLib = None
try:
    import bluetooth
    from bluetooth import BluetoothSocket, RFCOMM
except Exception:
    bluetooth = None
    BluetoothSocket = None
    RFCOMM = None


class BluetoothManager:
    """Bluetooth manager with basic BlueZ DBus integration.

    This manager configures the adapter (discoverable/pairable), watches
    devices via DBus signals, and exposes high-level operations such as
    `pair_device`, `connect_device`, and callback registration for
    connection events.

    When `pydbus`/`glib` are unavailable the manager runs in a safe stub
    mode so the application is still usable for development.
    """

    def __init__(self, cfg: ConfigParser, logger: logging.Logger = None):
        self.cfg = cfg
        self.logger = logger or logging.getLogger("BluetoothManager")
        self._bus = None
        self._adapter_path = None
        self._callbacks: List[Callable[[str, Dict], None]] = []
        self._device_paths: Dict[str, str] = {}
        self._running = False
        self._rfcomm_sock = None
        self._rfcomm_thread = None
        self._rfcomm_reader_thread = None
        self._rfcomm_reader_stop = threading.Event()
        # Call state and indicators tracked from AT responses
        self._indicators: Dict[str, int] = {}
        self._call_state: str = "idle"  # idle, incoming, active, held
        # default indicator mapping indices -> names (can be device-specific)
        # Typical order: service(0), call(1), callsetup(2), callheld(3)
        self._ciev_map = {0: "service", 1: "call", 2: "callsetup", 3: "callheld"}

    def start(self):
        self.logger.info("BluetoothManager starting")
        if SystemBus is None:
            self.logger.info("pydbus not available; attempting system fallback using bluetoothctl")
            # Try to power on and make adapter discoverable using bluetoothctl as a fallback
            try:
                import subprocess
                cmds = [
                    "power on",
                    "agent NoInputNoOutput",
                    "default-agent",
                    "pairable on",
                    "discoverable on",
                ]
                proc = subprocess.Popen(["bluetoothctl"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                out, err = proc.communicate("\n".join(cmds) + "\n")
                self.logger.debug("bluetoothctl output: %s", out)
                if err:
                    self.logger.debug("bluetoothctl errors: %s", err)
                self.logger.info("Bluetooth adapter attempted to be powered and set discoverable via bluetoothctl")
            except FileNotFoundError:
                self.logger.warning("bluetoothctl not found; cannot set adapter discoverable via CLI")
            except Exception:
                self.logger.exception("Failed to run bluetoothctl fallback commands")
            return

        try:
            self._bus = SystemBus()
            manager = self._bus.get("org.bluez", "/")
            # Find first adapter (commonly /org/bluez/hci0)
            obj_manager = self._bus.get("org.freedesktop.DBus.ObjectManager", "/")
        except Exception:
            self.logger.exception("Failed to connect to system bus or BlueZ")
            return

        # Locate adapter path
        try:
            objs = obj_manager.GetManagedObjects()
            for path, interfaces in objs.items():
                if "org.bluez.Adapter1" in interfaces:
                    self._adapter_path = path
                    break
            if not self._adapter_path:
                self.logger.error("No Bluetooth adapter found (org.bluez.Adapter1)")
                return

            adapter = self._bus.get("org.bluez", self._adapter_path)
            # Set discoverable and powered according to config
            discoverable = self.cfg.getboolean("bluetooth", "discoverable", fallback=True)
            adapter.Set("org.bluez.Adapter1", "Powered", True)
            adapter.Set("org.bluez.Adapter1", "Discoverable", discoverable)
            self.logger.info("Adapter %s set Powered=True Discoverable=%s", self._adapter_path, discoverable)

            # Listen to InterfacesAdded/Removed for device connect events
            def interfaces_added(path, interfaces):
                if "org.bluez.Device1" in interfaces:
                    props = interfaces["org.bluez.Device1"]
                    addr = props.get("Address")
                    self._device_paths[addr] = path
                    self.logger.info("Device discovered: %s -> %s", addr, path)

            def properties_changed(interface, changed, invalidated, path=None):
                if interface != "org.bluez.Device1":
                    return
                # changed may include Connected property
                if "Connected" in changed:
                    connected = bool(changed["Connected"])  # type: ignore
                    addr = None
                    # try to map path back to address
                    # this simplistic approach assumes previously discovered devices
                    for a, p in self._device_paths.items():
                        if p == path:
                            addr = a
                            break
                    self.logger.info("Device %s connected=%s", addr or path, connected)
                    for cb in self._callbacks:
                        try:
                            cb(path, {"connected": connected, "address": addr})
                        except Exception:
                            self.logger.exception("Callback error")

            # Connect signal handlers
            obj_manager.onInterfacesAdded = interfaces_added
            # PropertiesChanged signal is on org.freedesktop.DBus.Properties -- attach generic handler
            bus_proxy = self._bus.get("org.freedesktop.DBus.Properties", "/org/freedesktop/DBus")
            # pydbus makes it tricky to attach the generic signal — instead attach to adapter object
            adapter.onPropertiesChanged = properties_changed  # type: ignore

            self._running = True
        except Exception:
            self.logger.exception("Error during BlueZ setup")

    def stop(self):
        self.logger.info("BluetoothManager stopping")
        self._running = False

    def register_callback(self, cb: Callable[[str, Dict], None]):
        self._callbacks.append(cb)

    def pair_device(self, address: str) -> bool:
        """Attempt to pair with a device by Bluetooth address (XX:XX:...)."""
        if not self._adapter_path or self._bus is None:
            self.logger.warning("Cannot pair; adapter or bus not initialized")
            return False
        try:
            adapter = self._bus.get("org.bluez", self._adapter_path)
            # Use CreateDevice or call org.bluez.Adapter1.Pair? Adapter1 has StartDiscovery/CreateDevice depending on BlueZ
            adapter.StartDiscovery()
            self.logger.info("Started discovery for pairing %s", address)
        except Exception:
            self.logger.exception("Pairing attempt failed")
            return False
        return True

    def connect_device(self, address: str) -> bool:
        self.logger.info("connect_device requested: %s", address)
        # High-level connect: find device path and call Connect
        path = self._device_paths.get(address)
        if not path:
            self.logger.warning("Device %s not known; cannot connect", address)
            return False
        try:
            dev = self._bus.get("org.bluez", path)
            dev.Connect()
            # After connecting, attempt to open RFCOMM for AT commands (Hands-Free)
            try:
                self._open_rfcomm(address)
            except Exception:
                self.logger.debug("RFCOMM open failed or not available; continuing")
            return True
        except Exception:
            self.logger.exception("Failed to connect device %s", address)
            return False

    def disconnect_device(self, address: str) -> bool:
        path = self._device_paths.get(address)
        if not path:
            return False
        try:
            dev = self._bus.get("org.bluez", path)
            dev.Disconnect()
            # Close rfcomm socket if open
            try:
                self._close_rfcomm()
            except Exception:
                pass
            return True
        except Exception:
            self.logger.exception("Failed to disconnect device %s", address)
            return False

    def send_at(self, cmd: str) -> None:
        """Placeholder: sending AT commands over HFP is handled by BlueZ's
        internal profile code. Expose a method as integration point for
        `CallManager` — currently logs the command so higher-level code
        can be developed and tested without a live HFP RFCOMM socket.
        """
        self.logger.debug("AT command: %s", cmd)
        if self._rfcomm_sock:
            try:
                if not cmd.endswith("\r"):
                    cmd = cmd + "\r"
                self._rfcomm_sock.send(cmd.encode("utf-8"))
                self.logger.debug("Wrote AT to rfcomm socket")
            except Exception:
                self.logger.exception("Failed to send AT command over RFCOMM")

    def _open_rfcomm(self, address: str) -> bool:
        """Find a suitable RFCOMM channel (Handsfree/Headset) and open socket."""
        if bluetooth is None or BluetoothSocket is None:
            self.logger.debug("pybluez not available; cannot open RFCOMM")
            return False
        # search for Handsfree or Headset service
        services = []
        try:
            services = bluetooth.find_service(address=address)
        except Exception:
            self.logger.exception("Error during SDP search for %s", address)
            return False

        channel = None
        for s in services:
            name = (s.get("name") or "").lower()
            if "handsfree" in name or "headset" in name or s.get("protocol") == "RFCOMM":
                channel = s.get("port") or s.get("channel")
                break

        if channel is None:
            # No service found; attempt commonly used RFCOMM channel 1
            channel = 1

        try:
            sock = BluetoothSocket(RFCOMM)
            sock.connect((address, int(channel)))
            # set timeout to avoid blocking forever in read loop
            try:
                sock.settimeout(1.0)
            except Exception:
                pass
            self._rfcomm_sock = sock
            # start reader thread
            self._start_rfcomm_reader()
            self.logger.info("Opened RFCOMM to %s:%s", address, channel)
            return True
        except Exception:
            self.logger.exception("Failed to open RFCOMM socket to %s:%s", address, channel)
            self._rfcomm_sock = None
            return False

    def _close_rfcomm(self):
        try:
            if self._rfcomm_sock:
                try:
                    # stop reader thread first
                    self._stop_rfcomm_reader()
                except Exception:
                    pass
                try:
                    self._rfcomm_sock.close()
                except Exception:
                    pass
                self._rfcomm_sock = None
                self.logger.info("Closed RFCOMM socket")
        except Exception:
            self.logger.exception("Error closing RFCOMM socket")

    # RFCOMM reader and AT parsing
    def _start_rfcomm_reader(self):
        if not self._rfcomm_sock:
            return
        if self._rfcomm_reader_thread and self._rfcomm_reader_thread.is_alive():
            return
        self._rfcomm_reader_stop.clear()
        self._rfcomm_reader_thread = threading.Thread(target=self._rfcomm_reader_loop, daemon=True)
        self._rfcomm_reader_thread.start()

    def _stop_rfcomm_reader(self):
        try:
            self._rfcomm_reader_stop.set()
            if self._rfcomm_reader_thread:
                self._rfcomm_reader_thread.join(timeout=2.0)
        except Exception:
            pass

    def _rfcomm_reader_loop(self):
        buf = b""
        sock = self._rfcomm_sock
        self.logger.debug("RFCOMM reader loop started")
        while not self._rfcomm_reader_stop.is_set() and sock:
            try:
                data = sock.recv(1024)
                if not data:
                    # remote closed
                    time.sleep(0.1)
                    continue
                buf += data
                # split on CR or LF
                while b"\r" in buf or b"\n" in buf:
                    # find first terminator
                    idx_r = buf.find(b"\r") if b"\r" in buf else None
                    idx_n = buf.find(b"\n") if b"\n" in buf else None
                    idxs = [i for i in (idx_r, idx_n) if i is not None]
                    idx = min(idxs) if idxs else None
                    if idx is None:
                        break
                    line = buf[:idx].decode("utf-8", errors="ignore").strip()
                    buf = buf[idx+1:]
                    if line:
                        self._handle_at_line(line)
            except OSError:
                # socket timeout or non-blocking
                time.sleep(0.01)
                continue
            except Exception:
                self.logger.exception("Error in RFCOMM reader loop")
                break
        self.logger.debug("RFCOMM reader loop exiting")

    def _handle_at_line(self, line: str):
        """Parse a single AT-line received from the remote device and dispatch events."""
        self.logger.debug("RFCOMM received: %s", line)
        # Inform callbacks with parsed events
        # Examples: RING, +CIEV: (indicator), +VGS:, +VGM:, +CLCC:, OK, ERROR
        ev = None
        try:
            if line.upper() == "RING":
                ev = {"event": "ring"}
                # RING usually indicates an incoming call
                self._call_state = "incoming"
                # also dispatch call_state event
                for cb in self._callbacks:
                    try:
                        cb(None, {"event": "call_state", "state": "incoming"})
                    except Exception:
                        self.logger.exception("Callback error")
            elif line.upper() == "OK":
                ev = {"event": "ok"}
            elif line.upper().startswith("+CIEV:") or line.upper().startswith("+CIND:"):
                ev = {"event": "indicator", "value": line}
                # parse +CIEV: <index>,<value>
                try:
                    rest = line.split(":", 1)[1].strip()
                    parts = [p.strip() for p in rest.split(",") if p.strip()]
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        idx = int(parts[0])
                        val = int(parts[1])
                        name = self._ciev_map.get(idx, f"ind{idx}")
                        self._indicators[name] = val
                        ev["indicator"] = {"index": idx, "name": name, "value": val}
                except Exception:
                    self.logger.exception("Failed to parse +CIEV/ +CIND line")
            elif line.upper().startswith("+VGS:") or line.upper().startswith("+VGM:"):
                # remote volume set
                ev = {"event": "remote_volume", "value": line}
                # parse numeric value
                try:
                    import re
                    m = re.search(r"(\d+)", line)
                    if m:
                        ev["level"] = int(m.group(1))
                except Exception:
                    pass
            elif line.upper().startswith("+CLCC:"):
                ev = {"event": "clcc", "value": line}
                # parse CLCC to determine per-call status
                try:
                    # CLCC: <idx>,<dir>,<stat>,<mode>,<m>,"<number>",<type>
                    payload = line.split(":", 1)[1].strip()
                    # split by commas but keep quoted number together
                    import re
                    parts = re.findall(r'("[^"]*"|[^,]+)', payload)
                    if parts and len(parts) >= 3:
                        stat = parts[2].strip()
                        # status is an int
                        try:
                            st = int(stat)
                            # mapping: 0 active, 1 held, 2 dialing, 3 alerting, 4 incoming, 5 waiting
                            prev = self._call_state
                            if st == 4 or st == 5:
                                self._call_state = "incoming"
                            elif st == 0:
                                self._call_state = "active"
                            elif st == 1:
                                self._call_state = "held"
                            else:
                                # other states do not change
                                pass
                            # dispatch call_state event if changed
                            if self._call_state != prev:
                                for cb in self._callbacks:
                                    try:
                                        cb(None, {"event": "call_state", "state": self._call_state, "clcc": line})
                                    except Exception:
                                        self.logger.exception("Callback error")
                        except Exception:
                            pass
                except Exception:
                    self.logger.exception("Error parsing CLCC")
            elif line.upper().startswith("+BTRH:"):
                # +BTRH: <n>  - response & hold support/state
                try:
                    val = int(line.split(":", 1)[1].strip())
                    ev = {"event": "btrh", "value": val}
                except Exception:
                    ev = {"event": "btrh", "value": line}
            elif line.upper().startswith("+CNUM:"):
                # +CNUM: "Number",<type>,<service>
                try:
                    import re
                    m = re.search(r'\"([^\"]+)\"\s*,\s*(\d+)', line)
                    if m:
                        num = m.group(1)
                        typ = int(m.group(2))
                        ev = {"event": "cnum", "number": num, "type": typ}
                    else:
                        ev = {"event": "cnum", "value": line}
                except Exception:
                    ev = {"event": "cnum", "value": line}
            elif line.upper().startswith("+CLIP:"):
                # +CLIP: "<number>",<type>
                try:
                    import re
                    m = re.search(r'\"([^\"]+)\"\s*,\s*(\d+)', line)
                    if m:
                        num = m.group(1)
                        typ = int(m.group(2))
                        ev = {"event": "clip", "number": num, "type": typ}
                    else:
                        ev = {"event": "clip", "value": line}
                except Exception:
                    ev = {"event": "clip", "value": line}
            else:
                # Generic AT response
                ev = {"event": "line", "value": line}
        except Exception:
            self.logger.exception("Error parsing AT line")
            ev = {"event": "line", "value": line}

        # dispatch to callbacks
        for cb in self._callbacks:
            try:
                cb(None, ev)
            except Exception:
                self.logger.exception("Callback error while dispatching AT event")

