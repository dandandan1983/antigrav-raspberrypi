#!/usr/bin/env python3
"""
Main Application for RPi Hands-Free Headset

This is the main application that orchestrates all components:
- Bluetooth connection management
- Audio I/O handling
- Call control
- GPIO interface
- Event coordination
"""

import logging
import signal
import sys
import os
from pathlib import Path
from gi.repository import GLib

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from bluetooth_manager import BluetoothManager, ConnectionState
from audio_manager import AudioManager, AudioState
from call_manager import CallManager, CallState
from gpio_controller import GPIOController, LEDState


class HandsFreeHeadset:
    """Main application class for the hands-free headset."""
    
    def __init__(self, config_file: str = "config.ini"):
        """
        Initialize the hands-free headset application.
        
        Args:
            config_file: Path to configuration file
        """
        # Load configuration
        self.config = get_config(config_file)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self.bluetooth = BluetoothManager(
            device_name=self.config.bt_device_name,
            device_class=self.config.bt_device_class,
            pin_code=self.config.bt_pin_code,
            enable_a2dp=self.config.get_bool('bluetooth', 'enable_a2dp', False)
        )
        
        self.audio = AudioManager(
            sample_rate=self.config.audio_sample_rate,
            channels=self.config.audio_channels,
            buffer_size=self.config.audio_buffer_size,
            enable_preprocessing=self.config.audio_enable_preprocessing,
            noise_reduction_level=self.config.audio_noise_reduction_level,
            enable_aec=self.config.audio_enable_aec,
            enable_agc=self.config.audio_enable_agc,
            agc_target_level=self.config.audio_agc_target_level,
            enable_highpass=self.config.audio_enable_highpass,
            highpass_cutoff=self.config.audio_highpass_cutoff,
            enable_monitoring=self.config.audio_enable_quality_monitoring
        )
        
        # Set codec information for monitoring
        if self.config.audio_enable_wideband:
            self.audio.set_codec_info("mSBC")
        else:
            self.audio.set_codec_info("CVSD")
        
        self.call_manager = CallManager()
        
        self.gpio = GPIOController(
            button_answer_pin=self.config.gpio_button_answer,
            button_reject_pin=self.config.gpio_button_reject,
            button_vol_up_pin=self.config.gpio_button_vol_up,
            button_vol_down_pin=self.config.gpio_button_vol_down,
            led_status_pin=self.config.gpio_led_status,
            led_call_pin=self.config.gpio_led_call,
            debounce_time=self.config.gpio_debounce_time / 1000.0
        )
        
        # Main loop
        self.mainloop: GLib.MainLoop = None
        
        # State
        self.connected_device = None
        self.hfp_fd = None  # RFCOMM file descriptor from HFP connection
        
        logging.info("HandsFreeHeadset application initialized")
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        handlers = []
        
        # Console handler
        if self.config.log_to_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
            )
            handlers.append(console_handler)
        
        # File handler
        try:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
            )
            handlers.append(file_handler)
        except PermissionError:
            logging.warning(f"Cannot write to log file: {self.config.log_file}")
        
        logging.basicConfig(
            level=log_level,
            handlers=handlers
        )
        
        logging.info(f"Logging configured: level={self.config.log_level}")
    
    def _setup_callbacks(self) -> None:
        """Setup event callbacks between components."""
        
        # Bluetooth callbacks
        self.bluetooth.on_connected = self._handle_bt_connected
        self.bluetooth.on_disconnected = self._handle_bt_disconnected
        self.bluetooth.on_hfp_connected = self._handle_hfp_connected
        
        # Call manager callbacks
        self.call_manager.on_incoming_call = self._handle_incoming_call
        self.call_manager.on_call_answered = self._handle_call_answered
        self.call_manager.on_call_ended = self._handle_call_ended
        self.call_manager.on_volume_changed = self._handle_volume_changed
        
        # GPIO callbacks
        self.gpio.on_answer_pressed = self._handle_answer_button
        self.gpio.on_reject_pressed = self._handle_reject_button
        self.gpio.on_vol_up_pressed = self._handle_vol_up_button
        self.gpio.on_vol_down_pressed = self._handle_vol_down_button
        
        # Audio callbacks
        self.audio.on_audio_data = self._handle_audio_data
        
        logging.info("Event callbacks configured")
    
    # Bluetooth event handlers
    def _handle_bt_connected(self, device_address: str) -> None:
        """Handle Bluetooth device connection."""
        logging.info(f"Device connected: {device_address}")
        self.connected_device = device_address
        
        # Update LED
        self.gpio.indicate_connected()
        
        # Configure audio routing
        self.audio.route_to_bluetooth(device_address)
    
    def _handle_hfp_connected(self, device_address: str, fd: int) -> None:
        """Handle HFP connection with RFCOMM file descriptor."""
        logging.info(f"HFP connected: {device_address}, fd={fd}")
        self.hfp_fd = fd
        self.connected_device = device_address
        
        # Update LED
        self.gpio.indicate_connected()
        
        # Configure audio routing
        self.audio.route_to_bluetooth(device_address)
        
        # Connect CallManager to the RFCOMM channel via file descriptor
        self.call_manager.connect_rfcomm_fd(fd)
        
        # Connect SCO for voice audio
        self.audio.connect_sco(device_address)
    
    def _handle_bt_disconnected(self, device_address: str) -> None:
        """Handle Bluetooth device disconnection."""
        logging.info(f"Device disconnected: {device_address}")
        self.connected_device = None
        self.hfp_fd = None
        
        # Update LED
        self.gpio.indicate_disconnected()
        
        # Stop audio
        self.audio.stop_audio_loop()
        self.audio.disconnect_sco()
        
        # Disconnect RFCOMM
        self.call_manager.disconnect_rfcomm()
    
    # Call event handlers
    def _handle_incoming_call(self) -> None:
        """Handle incoming call."""
        logging.info("Incoming call detected")
        
        # Update LED
        self.gpio.indicate_incoming_call()
        
        # Could add ringtone playback here
    
    def _handle_call_answered(self) -> None:
        """Handle call answered."""
        logging.info("Call answered")
        
        # Update LED
        self.gpio.indicate_active_call()
        
        # Start audio loop
        self.audio.start_audio_loop()
    
    def _handle_call_ended(self) -> None:
        """Handle call ended."""
        logging.info("Call ended")
        
        # Update LED
        self.gpio.indicate_connected()
        
        # Stop audio loop
        self.audio.stop_audio_loop()
    
    def _handle_volume_changed(self, device: str, volume: int) -> None:
        """Handle volume change from phone."""
        logging.info(f"Volume changed: {device} = {volume}")
        
        if device == 'speaker':
            # Convert HFP volume (0-15) to system volume (0-100)
            system_volume = int((volume / 15) * 100)
            self.audio.set_speaker_volume(system_volume)
        elif device == 'microphone':
            system_volume = int((volume / 15) * 100)
            self.audio.set_microphone_volume(system_volume)
    
    # GPIO button handlers
    def _handle_answer_button(self) -> None:
        """Handle answer/hangup button press."""
        if self.call_manager.state == CallState.INCOMING:
            # Answer incoming call
            self.call_manager.answer_call()
        elif self.call_manager.state == CallState.ACTIVE:
            # Hang up active call
            self.call_manager.hangup_call()
    
    def _handle_reject_button(self) -> None:
        """Handle reject button press."""
        if self.call_manager.state == CallState.INCOMING:
            # Reject incoming call
            self.call_manager.reject_call()
    
    def _handle_vol_up_button(self) -> None:
        """Handle volume up button press."""
        self.audio.increase_volume()
        
        # Notify phone of volume change
        hfp_volume = int((self.audio.speaker_volume / 100) * 15)
        self.call_manager.set_speaker_volume(hfp_volume)
    
    def _handle_vol_down_button(self) -> None:
        """Handle volume down button press."""
        self.audio.decrease_volume()
        
        # Notify phone of volume change
        hfp_volume = int((self.audio.speaker_volume / 100) * 15)
        self.call_manager.set_speaker_volume(hfp_volume)
    
    # Audio handlers
    def _handle_audio_data(self, data: bytes) -> None:
        """Handle captured audio data from microphone."""
        # In production, this would send data to Bluetooth SCO
        # For now, just log that we're capturing
        logging.debug(f"Captured {len(data)} bytes of audio")
    
    # Application lifecycle
    def initialize(self) -> bool:
        """
        Initialize all components.
        
        Returns:
            True if successful
        """
        logging.info("Initializing application...")
        
        # Initialize Bluetooth
        if not self.bluetooth.initialize():
            logging.error("Failed to initialize Bluetooth")
            return False
        
        # Initialize audio
        if not self.audio.initialize():
            logging.error("Failed to initialize audio")
            return False
        
        # Initialize call manager
        if not self.call_manager.initialize():
            logging.error("Failed to initialize call manager")
            return False
        
        # Initialize GPIO
        if not self.gpio.initialize():
            logging.error("Failed to initialize GPIO")
            return False
        
        # Setup callbacks
        self._setup_callbacks()
        
        # Configure Bluetooth
        self.bluetooth.set_discoverable(
            self.config.bt_discoverable,
            timeout=0  # Always discoverable
        )
        self.bluetooth.set_pairable(True, timeout=0)
        
        # Set initial LED state
        self.gpio.indicate_disconnected()
        
        logging.info("Application initialized successfully")
        return True
    
    def run(self) -> None:
        """Run the application main loop."""
        logging.info("Starting application...")
        
        # Create main loop
        self.mainloop = GLib.MainLoop()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        try:
            logging.info("Application running. Press Ctrl+C to exit.")
            self.mainloop.run()
        except KeyboardInterrupt:
            logging.info("Received keyboard interrupt")
    
    def _signal_handler(self, sig, frame) -> None:
        """Handle termination signals."""
        logging.info(f"Received signal {sig}")
        self.shutdown()
    
    def shutdown(self) -> None:
        """Shutdown the application."""
        logging.info("Shutting down application...")
        
        # Stop main loop
        if self.mainloop:
            self.mainloop.quit()
        
        # Cleanup components
        self.call_manager.cleanup()
        self.audio.cleanup()
        self.bluetooth.cleanup()
        self.gpio.cleanup()
        
        logging.info("Application shutdown complete")
        sys.exit(0)


def main():
    """Main entry point."""
    # Change to project directory
    project_dir = Path(__file__).parent.parent
    os.chdir(project_dir)
    
    # Create application
    app = HandsFreeHeadset()
    
    # Initialize
    if not app.initialize():
        logging.error("Failed to initialize application")
        sys.exit(1)
    
    # Run
    app.run()


if __name__ == "__main__":
    main()
