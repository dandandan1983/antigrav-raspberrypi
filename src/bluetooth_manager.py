#!/usr/bin/env python3
"""
Bluetooth Manager Module for RPi Hands-Free Headset

This module manages Bluetooth connectivity using BlueZ via D-Bus.
It handles:
- Adapter initialization and configuration
- Device discovery and pairing
- HSP/HFP profile registration
- A2DP profile registration (optional)
- Bluetooth Agent for PIN authentication
- Connection state management
- Event callbacks
"""

import logging
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib
from typing import Optional, Callable, Dict, List
from enum import Enum
import os
import threading
import time


class ConnectionState(Enum):
    """Bluetooth connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PAIRING = "pairing"


# D-Bus interface constants
BLUEZ_SERVICE = 'org.bluez'
ADAPTER_INTERFACE = 'org.bluez.Adapter1'
DEVICE_INTERFACE = 'org.bluez.Device1'
PROFILE_MANAGER_INTERFACE = 'org.bluez.ProfileManager1'
AGENT_MANAGER_INTERFACE = 'org.bluez.AgentManager1'
AGENT_INTERFACE = 'org.bluez.Agent1'
PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'
OBJECT_MANAGER_INTERFACE = 'org.freedesktop.DBus.ObjectManager'

AGENT_PATH = "/org/bluez/handsfree/agent"
HFP_PROFILE_PATH = "/org/bluez/handsfree/hfp"
HSP_PROFILE_PATH = "/org/bluez/handsfree/hsp"
A2DP_PROFILE_PATH = "/org/bluez/handsfree/a2dp"


class BluetoothAgent(dbus.service.Object):
    """
    Bluetooth Agent for handling pairing requests.
    Implements org.bluez.Agent1 interface.
    """
    
    def __init__(self, bus: dbus.SystemBus, path: str, pin_code: str = "0000"):
        """
        Initialize Bluetooth Agent.
        
        Args:
            bus: D-Bus system bus
            path: D-Bus object path for agent
            pin_code: PIN code for pairing
        """
        super().__init__(bus, path)
        self.pin_code = pin_code
        self.bus = bus
        logging.info(f"BluetoothAgent created at {path}")
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self):
        """Called when agent is unregistered."""
        logging.info("Agent released")
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device: str, uuid: str):
        """Authorize a service on a device."""
        logging.info(f"AuthorizeService: device={device}, uuid={uuid}")
        # Auto-authorize HFP, HSP, A2DP services
        return
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device: str) -> str:
        """Return PIN code for pairing."""
        logging.info(f"RequestPinCode for {device}, returning {self.pin_code}")
        return self.pin_code
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device: str) -> int:
        """Return passkey for pairing."""
        logging.info(f"RequestPasskey for {device}")
        return int(self.pin_code)
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device: str, passkey: int, entered: int):
        """Display passkey during pairing."""
        logging.info(f"DisplayPasskey: device={device}, passkey={passkey:06d}")
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device: str, pincode: str):
        """Display PIN code during pairing."""
        logging.info(f"DisplayPinCode: device={device}, pincode={pincode}")
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device: str, passkey: int):
        """Confirm passkey match."""
        logging.info(f"RequestConfirmation: device={device}, passkey={passkey:06d}")
        # Auto-confirm
        return
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device: str):
        """Authorize device connection."""
        logging.info(f"RequestAuthorization for {device}")
        # Auto-authorize
        return
    
    @dbus.service.method(AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self):
        """Cancel ongoing pairing."""
        logging.info("Agent pairing cancelled")


class HFPProfile(dbus.service.Object):
    """
    HFP (Hands-Free Profile) implementation.
    Implements org.bluez.Profile1 interface.
    """
    
    def __init__(self, bus: dbus.SystemBus, path: str, 
                 on_connect: Optional[Callable] = None,
                 on_disconnect: Optional[Callable] = None):
        """
        Initialize HFP Profile.
        
        Args:
            bus: D-Bus system bus
            path: D-Bus object path
            on_connect: Callback when device connects
            on_disconnect: Callback when device disconnects
        """
        super().__init__(bus, path)
        self.bus = bus
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.fd = None
        self.device_path = None
        logging.info(f"HFPProfile created at {path}")
    
    @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
    def Release(self):
        """Called when profile is unregistered."""
        logging.info("HFP Profile released")
    
    @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
    def NewConnection(self, device: str, fd: int, properties: dict):
        """
        Called when new connection is established.
        
        Args:
            device: D-Bus path of connected device
            fd: File descriptor for RFCOMM channel
            properties: Connection properties
        """
        self.fd = os.dup(fd)  # Duplicate fd to keep it open
        self.device_path = device
        
        # Extract device address from path
        device_address = device.split('/')[-1].replace('_', ':')
        
        logging.info(f"HFP NewConnection: device={device_address}, fd={self.fd}")
        logging.debug(f"Connection properties: {properties}")
        
        if self.on_connect:
            self.on_connect(device_address, self.fd)
    
    @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
    def RequestDisconnection(self, device: str):
        """Called when disconnection is requested."""
        logging.info(f"HFP RequestDisconnection: {device}")
        
        if self.fd:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        
        device_address = device.split('/')[-1].replace('_', ':')
        
        if self.on_disconnect:
            self.on_disconnect(device_address)
        
        self.device_path = None


class BluetoothManager:
    """Manages Bluetooth connectivity and HFP/HSP profiles."""
    
    # Bluetooth service UUIDs
    HSP_AG_UUID = "00001112-0000-1000-8000-00805f9b34fb"  # Headset Audio Gateway
    HFP_AG_UUID = "0000111f-0000-1000-8000-00805f9b34fb"  # Hands-Free Audio Gateway
    HSP_UUID = "00001108-0000-1000-8000-00805f9b34fb"     # Headset
    HFP_UUID = "0000111e-0000-1000-8000-00805f9b34fb"     # Hands-Free
    A2DP_SINK_UUID = "0000110b-0000-1000-8000-00805f9b34fb"  # A2DP Sink
    A2DP_SOURCE_UUID = "0000110a-0000-1000-8000-00805f9b34fb"  # A2DP Source
    
    def __init__(self, device_name: str = "RPi Hands-Free", 
                 device_class: str = "0x200404",
                 pin_code: str = "0000",
                 enable_a2dp: bool = False):
        """
        Initialize Bluetooth Manager.
        
        Args:
            device_name: Name to advertise to other devices
            device_class: Bluetooth device class (0x200404 = Hands-Free audio)
            pin_code: PIN code for pairing
            enable_a2dp: Enable A2DP profile (mutually exclusive with HFP during call)
        """
        self.device_name = device_name
        self.device_class = device_class
        self.pin_code = pin_code
        self.enable_a2dp = enable_a2dp
        self.state = ConnectionState.DISCONNECTED
        self.connected_device = None
        self.connected_device_address = None
        
        # Reconnection settings
        self.auto_reconnect = True
        self.reconnect_attempts = 5
        self.reconnect_delay = 2.0
        self.reconnect_max_delay = 30.0
        self._reconnect_thread: Optional[threading.Thread] = None
        self._stop_reconnect = threading.Event()
        self._last_connected_device: Optional[str] = None  # D-Bus path
        
        # Callbacks
        self.on_connected: Optional[Callable] = None
        self.on_disconnected: Optional[Callable] = None
        self.on_device_found: Optional[Callable] = None
        self.on_hfp_connected: Optional[Callable] = None  # HFP specific with fd
        
        # D-Bus objects
        self.bus: Optional[dbus.SystemBus] = None
        self.adapter: Optional[dbus.Interface] = None
        self.adapter_props: Optional[dbus.Interface] = None
        self.adapter_path: Optional[str] = None
        
        # Agent and profiles
        self.agent: Optional[BluetoothAgent] = None
        self.hfp_profile: Optional[HFPProfile] = None
        self.profiles_registered = False
        
        # Initialize D-Bus
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        
        logging.info("BluetoothManager initialized")
    
    def initialize(self) -> bool:
        """
        Initialize Bluetooth adapter.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get system bus
            self.bus = dbus.SystemBus()
            
            # Get adapter object
            self.adapter_path = self._find_adapter()
            if not self.adapter_path:
                logging.error("No Bluetooth adapter found")
                return False
            
            adapter_obj = self.bus.get_object(BLUEZ_SERVICE, self.adapter_path)
            self.adapter = dbus.Interface(adapter_obj, ADAPTER_INTERFACE)
            self.adapter_props = dbus.Interface(adapter_obj, PROPERTIES_INTERFACE)
            
            # Configure adapter
            self._configure_adapter()
            
            # Power on adapter
            self.adapter_props.Set(ADAPTER_INTERFACE, 'Powered', dbus.Boolean(True))
            
            # Register agent for pairing
            if not self.register_agent(self.pin_code):
                logging.warning("Agent registration failed, pairing may not work")
            
            # Register HFP/HSP profiles
            # Note: This may fail if oFono or PulseAudio already registered these UUIDs
            # In that case, the application can still work with the existing profile handlers
            self._register_profiles()
            
            # Setup signal handlers for device events
            self._setup_signal_handlers()
            
            logging.info(f"Bluetooth adapter initialized: {self.adapter_path}")
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to initialize Bluetooth adapter: {e}")
            return False
    
    def _setup_signal_handlers(self) -> None:
        """Setup D-Bus signal handlers for device events."""
        try:
            self.bus.add_signal_receiver(
                self._on_properties_changed,
                dbus_interface=PROPERTIES_INTERFACE,
                signal_name="PropertiesChanged",
                path_keyword="path"
            )
            
            self.bus.add_signal_receiver(
                self._on_interfaces_added,
                dbus_interface=OBJECT_MANAGER_INTERFACE,
                signal_name="InterfacesAdded"
            )
            
            logging.info("D-Bus signal handlers registered")
        except Exception as e:
            logging.error(f"Failed to setup signal handlers: {e}")
    
    def _on_properties_changed(self, interface: str, changed: dict, 
                               invalidated: list = None, path: str = None) -> None:
        """Handle property changes on Bluetooth devices."""
        if interface != DEVICE_INTERFACE:
            return
        
        if 'Connected' in changed:
            device_obj = self.bus.get_object(BLUEZ_SERVICE, path)
            device_props = dbus.Interface(device_obj, PROPERTIES_INTERFACE)
            
            try:
                address = str(device_props.Get(DEVICE_INTERFACE, 'Address'))
                name = str(device_props.Get(DEVICE_INTERFACE, 'Name'))
            except:
                address = path.split('/')[-1].replace('_', ':')
                name = "Unknown"
            
            if changed['Connected']:
                logging.info(f"Device connected: {name} ({address})")
                self.state = ConnectionState.CONNECTED
                self.connected_device = path
                self.connected_device_address = address
                self._last_connected_device = path
                self._stop_reconnect.set()  # Stop any reconnection attempts
                
                if self.on_connected:
                    self.on_connected(address)
            else:
                logging.info(f"Device disconnected: {name} ({address})")
                self.state = ConnectionState.DISCONNECTED
                self.connected_device = None
                self.connected_device_address = None
                
                if self.on_disconnected:
                    self.on_disconnected(address)
                
                # Start auto-reconnect if enabled
                if self.auto_reconnect and self._last_connected_device:
                    self._start_reconnect_thread()
    
    def _on_interfaces_added(self, path: str, interfaces: dict) -> None:
        """Handle new interfaces added (device discovery)."""
        if DEVICE_INTERFACE not in interfaces:
            return
        
        props = interfaces[DEVICE_INTERFACE]
        address = str(props.get('Address', ''))
        name = str(props.get('Name', 'Unknown'))
        
        logging.info(f"Device found: {name} ({address})")
        
        if self.on_device_found:
            self.on_device_found(address, name)
    
    def _find_adapter(self) -> Optional[str]:
        """
        Find Bluetooth adapter path.
        
        Returns:
            Adapter D-Bus path or None if not found
        """
        try:
            manager = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, '/'),
                OBJECT_MANAGER_INTERFACE
            )
            objects = manager.GetManagedObjects()
            
            for path, interfaces in objects.items():
                if ADAPTER_INTERFACE in interfaces:
                    return path
            
            return None
        except dbus.exceptions.DBusException as e:
            logging.error(f"Error finding adapter: {e}")
            return None
    
    def _configure_adapter(self) -> None:
        """Configure adapter with device name and class."""
        try:
            # Set device name
            self.adapter_props.Set(
                ADAPTER_INTERFACE, 
                'Alias', 
                dbus.String(self.device_name)
            )
            
            # Set device class (if supported)
            try:
                self.adapter_props.Set(
                    ADAPTER_INTERFACE,
                    'Class',
                    dbus.UInt32(int(self.device_class, 16))
                )
            except dbus.exceptions.DBusException:
                logging.warning("Setting device class not supported on this system")
            
            logging.info(f"Adapter configured: {self.device_name}")
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to configure adapter: {e}")
    
    def _unregister_profile_safe(self, profile_manager, path: str) -> None:
        """
        Safely unregister a profile, ignoring errors if not registered.
        
        Args:
            profile_manager: D-Bus ProfileManager interface
            path: Profile object path to unregister
        """
        try:
            profile_manager.UnregisterProfile(dbus.ObjectPath(path))
            logging.debug(f"Unregistered existing profile at {path}")
        except dbus.exceptions.DBusException:
            pass  # Profile wasn't registered, that's fine
    
    def _register_profiles(self) -> bool:
        """
        Register HFP/HSP profiles with BlueZ.
        
        Returns:
            True if successful
        """
        try:
            # Get ProfileManager
            profile_manager = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, '/org/bluez'),
                PROFILE_MANAGER_INTERFACE
            )
            
            # First, try to unregister any existing profiles at our paths
            # This handles the case where a previous run didn't clean up
            self._unregister_profile_safe(profile_manager, HFP_PROFILE_PATH)
            self._unregister_profile_safe(profile_manager, HSP_PROFILE_PATH)
            if self.enable_a2dp:
                self._unregister_profile_safe(profile_manager, A2DP_PROFILE_PATH)
            
            # Create HFP profile handler
            self.hfp_profile = HFPProfile(
                self.bus, 
                HFP_PROFILE_PATH,
                on_connect=self._on_hfp_connected,
                on_disconnect=self._on_hfp_disconnected
            )
            
            # HFP profile options
            hfp_options = {
                "Name": dbus.String("Hands-Free"),
                "Role": dbus.String("client"),  # We act as HFP HF (client to phone's AG)
                "Channel": dbus.UInt16(1),
                "Features": dbus.UInt16(0x3F),  # Support all features
                "Version": dbus.UInt16(0x0108),  # HFP 1.8
            }
            
            hfp_registered = False
            hsp_registered = False
            
            # Register HFP profile
            try:
                profile_manager.RegisterProfile(
                    dbus.ObjectPath(HFP_PROFILE_PATH),
                    self.HFP_UUID,
                    hfp_options
                )
                logging.info("HFP profile registered")
                hfp_registered = True
            except dbus.exceptions.DBusException as e:
                error_name = e.get_dbus_name() if hasattr(e, 'get_dbus_name') else str(e)
                if "AlreadyExists" in str(e) or "UUID already registered" in str(e):
                    logging.warning("HFP UUID already registered by another service (e.g., oFono/PulseAudio)")
                    logging.info("Will use existing HFP profile - ensure oFono or pulseaudio-bluetooth is configured")
                else:
                    logging.error(f"HFP registration failed: {e}")
            
            # Also register HSP for fallback
            hsp_options = {
                "Name": dbus.String("Headset"),
                "Role": dbus.String("client"),
                "Channel": dbus.UInt16(2),
            }
            
            try:
                profile_manager.RegisterProfile(
                    dbus.ObjectPath(HSP_PROFILE_PATH),
                    self.HSP_UUID,
                    hsp_options
                )
                logging.info("HSP profile registered")
                hsp_registered = True
            except dbus.exceptions.DBusException as e:
                if "AlreadyExists" in str(e) or "UUID already registered" in str(e):
                    logging.warning("HSP UUID already registered by another service")
                else:
                    logging.warning(f"HSP registration failed (non-critical): {e}")
            
            # Register A2DP if enabled
            if self.enable_a2dp:
                try:
                    a2dp_options = {
                        "Name": dbus.String("Audio Sink"),
                        "Role": dbus.String("client"),
                    }
                    profile_manager.RegisterProfile(
                        dbus.ObjectPath(A2DP_PROFILE_PATH),
                        self.A2DP_SINK_UUID,
                        a2dp_options
                    )
                    logging.info("A2DP Sink profile registered")
                except dbus.exceptions.DBusException as e:
                    logging.warning(f"A2DP registration failed: {e}")
            
            # Mark as registered if at least one profile was registered
            # or if they're handled by another service
            self.profiles_registered = True
            
            if not hfp_registered and not hsp_registered:
                logging.warning(
                    "No HFP/HSP profiles registered directly. "
                    "Bluetooth hands-free may still work via oFono/PulseAudio."
                )
            
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to register profiles: {e}")
            return False
    
    def _on_hfp_connected(self, device_address: str, fd: int) -> None:
        """Handle HFP connection with RFCOMM file descriptor."""
        logging.info(f"HFP connected: {device_address}, fd={fd}")
        self.state = ConnectionState.CONNECTED
        self.connected_device_address = device_address
        
        if self.on_hfp_connected:
            self.on_hfp_connected(device_address, fd)
    
    def _on_hfp_disconnected(self, device_address: str) -> None:
        """Handle HFP disconnection."""
        logging.info(f"HFP disconnected: {device_address}")
        # on_disconnected callback will be triggered by property change
    
    def set_discoverable(self, discoverable: bool, timeout: int = 0) -> bool:
        """
        Set adapter discoverable mode.
        
        Args:
            discoverable: Whether to make device discoverable
            timeout: Discovery timeout in seconds (0 = no timeout)
            
        Returns:
            True if successful
        """
        try:
            self.adapter_props.Set(
                ADAPTER_INTERFACE,
                'Discoverable',
                dbus.Boolean(discoverable)
            )
            
            self.adapter_props.Set(
                ADAPTER_INTERFACE,
                'DiscoverableTimeout',
                dbus.UInt32(timeout)
            )
            
            logging.info(f"Discoverable mode: {discoverable}")
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to set discoverable mode: {e}")
            return False
    
    def set_pairable(self, pairable: bool, timeout: int = 0) -> bool:
        """
        Set adapter pairable mode.
        
        Args:
            pairable: Whether to make device pairable
            timeout: Pairable timeout in seconds (0 = no timeout)
            
        Returns:
            True if successful
        """
        try:
            self.adapter_props.Set(
                ADAPTER_INTERFACE,
                'Pairable',
                dbus.Boolean(pairable)
            )
            
            self.adapter_props.Set(
                ADAPTER_INTERFACE,
                'PairableTimeout',
                dbus.UInt32(timeout)
            )
            
            logging.info(f"Pairable mode: {pairable}")
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to set pairable mode: {e}")
            return False
    
    def start_discovery(self) -> bool:
        """
        Start device discovery.
        
        Returns:
            True if successful
        """
        try:
            self.adapter.StartDiscovery()
            logging.info("Device discovery started")
            return True
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to start discovery: {e}")
            return False
    
    def stop_discovery(self) -> bool:
        """
        Stop device discovery.
        
        Returns:
            True if successful
        """
        try:
            self.adapter.StopDiscovery()
            logging.info("Device discovery stopped")
            return True
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to stop discovery: {e}")
            return False
    
    def get_paired_devices(self) -> list:
        """
        Get list of paired devices.
        
        Returns:
            List of paired device dictionaries
        """
        devices = []
        try:
            manager = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, '/'),
                OBJECT_MANAGER_INTERFACE
            )
            objects = manager.GetManagedObjects()
            
            for path, interfaces in objects.items():
                if DEVICE_INTERFACE in interfaces:
                    device_props = interfaces[DEVICE_INTERFACE]
                    if device_props.get('Paired', False):
                        devices.append({
                            'path': path,
                            'address': str(device_props.get('Address', '')),
                            'name': str(device_props.get('Name', 'Unknown')),
                            'connected': device_props.get('Connected', False)
                        })
            
            return devices
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to get paired devices: {e}")
            return []
    
    def connect_device(self, device_path: str) -> bool:
        """
        Connect to a specific device.
        
        Args:
            device_path: D-Bus path of the device
            
        Returns:
            True if connection initiated successfully
        """
        try:
            device = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, device_path),
                DEVICE_INTERFACE
            )
            device.Connect()
            
            self.state = ConnectionState.CONNECTING
            logging.info(f"Connecting to device: {device_path}")
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to connect to device: {e}")
            return False
    
    def disconnect_device(self, device_path: str) -> bool:
        """
        Disconnect from a specific device.
        
        Args:
            device_path: D-Bus path of the device
            
        Returns:
            True if disconnection initiated successfully
        """
        try:
            device = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, device_path),
                DEVICE_INTERFACE
            )
            device.Disconnect()
            
            logging.info(f"Disconnecting from device: {device_path}")
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to disconnect from device: {e}")
            return False
    
    def register_agent(self, pin_code: str = "0000") -> bool:
        """
        Register pairing agent with PIN code.
        
        Args:
            pin_code: PIN code for pairing
            
        Returns:
            True if successful
        """
        try:
            # Create agent
            self.agent = BluetoothAgent(self.bus, AGENT_PATH, pin_code)
            
            # Get AgentManager
            agent_manager = dbus.Interface(
                self.bus.get_object(BLUEZ_SERVICE, '/org/bluez'),
                AGENT_MANAGER_INTERFACE
            )
            
            # Register agent
            agent_manager.RegisterAgent(dbus.ObjectPath(AGENT_PATH), "NoInputNoOutput")
            
            # Request to be default agent
            agent_manager.RequestDefaultAgent(dbus.ObjectPath(AGENT_PATH))
            
            logging.info(f"Bluetooth agent registered with PIN: {pin_code}")
            return True
            
        except dbus.exceptions.DBusException as e:
            logging.error(f"Failed to register agent: {e}")
            return False
    
    def configure_reconnect(self, auto_reconnect: bool = True,
                           attempts: int = 5, delay: float = 2.0,
                           max_delay: float = 30.0) -> None:
        """
        Configure auto-reconnect settings.
        
        Args:
            auto_reconnect: Enable/disable auto-reconnect
            attempts: Number of reconnection attempts
            delay: Initial delay between attempts (seconds)
            max_delay: Maximum delay with exponential backoff
        """
        self.auto_reconnect = auto_reconnect
        self.reconnect_attempts = attempts
        self.reconnect_delay = delay
        self.reconnect_max_delay = max_delay
        logging.info(f"Reconnect config: enabled={auto_reconnect}, attempts={attempts}")
    
    def _start_reconnect_thread(self) -> None:
        """Start reconnection thread with exponential backoff."""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            logging.debug("Reconnect thread already running")
            return
        
        self._stop_reconnect.clear()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop,
            daemon=True
        )
        self._reconnect_thread.start()
        logging.info("Auto-reconnect started")
    
    def _reconnect_loop(self) -> None:
        """Reconnection loop with exponential backoff."""
        current_delay = self.reconnect_delay
        
        for attempt in range(1, self.reconnect_attempts + 1):
            if self._stop_reconnect.is_set():
                logging.info("Reconnect cancelled")
                return
            
            if self.state == ConnectionState.CONNECTED:
                logging.info("Already connected, stopping reconnect")
                return
            
            logging.info(f"Reconnect attempt {attempt}/{self.reconnect_attempts} "
                        f"(delay: {current_delay:.1f}s)")
            
            # Wait before attempting
            if self._stop_reconnect.wait(timeout=current_delay):
                logging.info("Reconnect cancelled during wait")
                return
            
            # Try to connect
            if self._last_connected_device:
                try:
                    if self.connect_device(self._last_connected_device):
                        # Wait a bit for connection to establish
                        time.sleep(2.0)
                        if self.state == ConnectionState.CONNECTED:
                            logging.info("Reconnect successful")
                            return
                except Exception as e:
                    logging.warning(f"Reconnect attempt failed: {e}")
            
            # Exponential backoff
            current_delay = min(current_delay * 1.5, self.reconnect_max_delay)
        
        logging.warning(f"Reconnect failed after {self.reconnect_attempts} attempts")
    
    def stop_reconnect(self) -> None:
        """Stop any ongoing reconnection attempts."""
        self._stop_reconnect.set()
        if self._reconnect_thread:
            self._reconnect_thread.join(timeout=2.0)
            self._reconnect_thread = None
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Stop reconnection thread
            self.stop_reconnect()
            
            # Unregister profiles
            if self.profiles_registered and self.bus:
                try:
                    profile_manager = dbus.Interface(
                        self.bus.get_object(BLUEZ_SERVICE, '/org/bluez'),
                        PROFILE_MANAGER_INTERFACE
                    )
                    profile_manager.UnregisterProfile(dbus.ObjectPath(HFP_PROFILE_PATH))
                    profile_manager.UnregisterProfile(dbus.ObjectPath(HSP_PROFILE_PATH))
                    if self.enable_a2dp:
                        profile_manager.UnregisterProfile(dbus.ObjectPath(A2DP_PROFILE_PATH))
                except:
                    pass
            
            # Unregister agent
            if self.agent and self.bus:
                try:
                    agent_manager = dbus.Interface(
                        self.bus.get_object(BLUEZ_SERVICE, '/org/bluez'),
                        AGENT_MANAGER_INTERFACE
                    )
                    agent_manager.UnregisterAgent(dbus.ObjectPath(AGENT_PATH))
                except:
                    pass
            
            if self.adapter:
                self.set_discoverable(False)
                self.set_pairable(False)
            
            logging.info("BluetoothManager cleaned up")
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
    
    def get_hfp_fd(self) -> Optional[int]:
        """
        Get HFP RFCOMM file descriptor for AT commands.
        
        Returns:
            File descriptor or None if not connected
        """
        if self.hfp_profile and self.hfp_profile.fd:
            return self.hfp_profile.fd
        return None


if __name__ == "__main__":
    # Test Bluetooth manager
    logging.basicConfig(level=logging.INFO)
    
    bt = BluetoothManager()
    if bt.initialize():
        bt.set_discoverable(True)
        bt.set_pairable(True)
        
        print("Paired devices:")
        for device in bt.get_paired_devices():
            print(f"  - {device['name']} ({device['address']})")
        
        bt.cleanup()
