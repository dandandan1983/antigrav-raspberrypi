#!/usr/bin/env python3
"""
Audio Manager Module for RPi Hands-Free Headset

This module manages audio input/output for the hands-free system.
It handles:
- Microphone capture
- Speaker output
- Audio routing for Bluetooth SCO
- Volume control
- Integration with ALSA/PulseAudio
"""

import logging
import subprocess
from typing import Optional, Callable
from enum import Enum
import threading
import time
import numpy as np
import os
import socket
from pulsectl import Pulse, PulseLoopStop

# Import audio enhancement modules
try:
    from audio_preprocessing import AudioPreprocessor
    from audio_monitor import AudioMonitor
    AUDIO_ENHANCEMENT_AVAILABLE = True
except ImportError:
    AUDIO_ENHANCEMENT_AVAILABLE = False
    logging.warning("Audio enhancement modules not available")


class AudioState(Enum):
    """Audio system states."""
    IDLE = "idle"
    CAPTURING = "capturing"
    PLAYING = "playing"
    ACTIVE_CALL = "active_call"


class AudioManager:
    """Manages audio input/output for the hands-free system."""
    
    # SCO socket constants
    BTPROTO_SCO = 2
    SOL_SCO = 17
    SCO_OPTIONS = 1
    
    def __init__(self, pulse_sink: str = 'hfp_sink', pulse_source: str = 'hfp_source',
                 sample_rate: int = 16000, channels: int = 1, 
                 buffer_size: int = 1024,
                 capture_device: str = 'default',
                 playback_device: str = 'default',
                 enable_preprocessing: bool = True,
                 noise_reduction_level: int = 2,
                 enable_aec: bool = True,
                 enable_agc: bool = True,
                 agc_target_level: float = -6.0,
                 enable_highpass: bool = True,
                 highpass_cutoff: float = 80.0,
                 enable_monitoring: bool = True,
                 aec_tail_ms: int = 200):
        """
        Initialize Audio Manager.
        
        Args:
            pulse_sink: PulseAudio sink name (e.g., 'hfp_sink')
            pulse_source: PulseAudio source name (e.g., 'hfp_source')
            sample_rate: Audio sample rate in Hz (8000 or 16000 for voice)
            channels: Number of audio channels (1 = mono, 2 = stereo)
            buffer_size: Audio buffer size in frames
            capture_device: ALSA capture device name (e.g., 'default', 'hw:1,0')
            playback_device: ALSA playback device name (e.g., 'default', 'hw:0,0')
            enable_preprocessing: Enable audio preprocessing pipeline
            noise_reduction_level: Noise reduction strength (0-3)
            enable_aec: Enable echo cancellation
            enable_agc: Enable automatic gain control
            agc_target_level: AGC target level in dB
            enable_highpass: Enable high-pass filter
            highpass_cutoff: High-pass filter cutoff in Hz
            enable_monitoring: Enable quality monitoring
            aec_tail_ms: Echo cancellation tail length in ms
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_size = buffer_size
        self.capture_device_name = capture_device
        self.playback_device_name = playback_device
        self.state = AudioState.IDLE
        self.aec_tail_ms = aec_tail_ms
        self.pulse_sink = pulse_sink
        self.pulse_source = pulse_source
        self.pulse = Pulse('AudioManager')
        
        # Audio devices
        self.capture_device: Optional[alsaaudio.PCM] = None
        self.playback_device: Optional[alsaaudio.PCM] = None
        
        # SCO audio socket for Bluetooth voice
        self.sco_socket: Optional[socket.socket] = None
        self.sco_mtu = 48  # Default SCO MTU
        
        # Volume levels (0-100)
        self.speaker_volume = 75
        self.microphone_volume = 75
        
        # Callbacks
        self.on_audio_data: Optional[Callable] = None
        
        # Threading with Event for thread-safe stop signal
        self.audio_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._audio_lock = threading.Lock()
        
        # Playback buffer for AEC reference
        self._playback_buffer: bytes = b''
        self._playback_lock = threading.Lock()
        
        # Audio enhancement components
        self.preprocessor: Optional[AudioPreprocessor] = None
        self.monitor: Optional[AudioMonitor] = None
        
        if AUDIO_ENHANCEMENT_AVAILABLE and enable_preprocessing:
            try:
                self.preprocessor = AudioPreprocessor(
                    sample_rate=sample_rate,
                    frame_size_ms=20,
                    enable_noise_reduction=(noise_reduction_level > 0),
                    noise_reduction_level=noise_reduction_level,
                    enable_aec=enable_aec,
                    enable_agc=enable_agc,
                    agc_target_level_db=agc_target_level,
                    enable_highpass=enable_highpass,
                    highpass_cutoff=highpass_cutoff
                )
                logging.info("Audio preprocessing enabled")
            except Exception as e:
                logging.error(f"Failed to initialize preprocessor: {e}")
        
        if AUDIO_ENHANCEMENT_AVAILABLE and enable_monitoring:
            try:
                self.monitor = AudioMonitor(sample_rate=sample_rate)
                logging.info("Audio quality monitoring enabled")
            except Exception as e:
                logging.error(f"Failed to initialize monitor: {e}")
        
        logging.info(f"AudioManager initialized: {sample_rate}Hz, {channels}ch")
    
    @staticmethod
    def list_audio_devices() -> dict:
        """
        List available audio devices.
        
        Returns:
            Dict with 'capture' and 'playback' device lists
        """
        try:
            capture_devices = alsaaudio.pcms(alsaaudio.PCM_CAPTURE)
            playback_devices = alsaaudio.pcms(alsaaudio.PCM_PLAYBACK)
            return {
                'capture': capture_devices,
                'playback': playback_devices
            }
        except Exception as e:
            logging.error(f"Failed to list audio devices: {e}")
            return {'capture': [], 'playback': []}
    
    def initialize(self) -> bool:
        """
        Initialize audio devices.
        
        Returns:
            True if successful
        """
        try:
            # Try to open capture device
            self.capture_device = alsaaudio.PCM(
                alsaaudio.PCM_CAPTURE,
                alsaaudio.PCM_NORMAL,
                device=self.capture_device_name
            )
            
            # Configure capture device
            self.capture_device.setchannels(self.channels)
            self.capture_device.setrate(self.sample_rate)
            self.capture_device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
            self.capture_device.setperiodsize(self.buffer_size)
            
            logging.info(f"Audio capture device initialized: {self.capture_device_name}")
            
            # Try to open playback device
            self.playback_device = alsaaudio.PCM(
                alsaaudio.PCM_PLAYBACK,
                alsaaudio.PCM_NORMAL,
                device=self.playback_device_name
            )
            
            # Configure playback device
            self.playback_device.setchannels(self.channels)
            self.playback_device.setrate(self.sample_rate)
            self.playback_device.setformat(alsaaudio.PCM_FORMAT_S16_LE)
            self.playback_device.setperiodsize(self.buffer_size)
            
            logging.info(f"Audio playback device initialized: {self.playback_device_name}")
            
            return True
            
        except alsaaudio.ALSAAudioError as e:
            logging.error(f"Failed to initialize audio devices: {e}")
            return False
    
    def set_speaker_volume(self, volume: int) -> bool:
        """
        Set speaker volume.
        
        Args:
            volume: Volume level (0-100)
            
        Returns:
            True if successful
        """
        try:
            volume = max(0, min(100, volume))  # Clamp to 0-100
            
            # Use amixer to set volume
            subprocess.run(
                ['amixer', 'sset', 'Master', f'{volume}%'],
                check=True,
                capture_output=True
            )
            
            self.speaker_volume = volume
            logging.info(f"Speaker volume set to {volume}%")
            return True
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to set speaker volume: {e}")
            return False
        except FileNotFoundError:
            logging.warning("amixer not found, volume control unavailable")
            return False
    
    def set_microphone_volume(self, volume: int) -> bool:
        """
        Set microphone volume.
        
        Args:
            volume: Volume level (0-100)
            
        Returns:
            True if successful
        """
        try:
            volume = max(0, min(100, volume))  # Clamp to 0-100
            
            # Use amixer to set capture volume
            subprocess.run(
                ['amixer', 'sset', 'Capture', f'{volume}%'],
                check=True,
                capture_output=True
            )
            
            self.microphone_volume = volume
            logging.info(f"Microphone volume set to {volume}%")
            return True
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to set microphone volume: {e}")
            return False
        except FileNotFoundError:
            logging.warning("amixer not found, volume control unavailable")
            return False
    
    def increase_volume(self, step: int = 10) -> bool:
        """
        Increase speaker volume.
        
        Args:
            step: Volume increment
            
        Returns:
            True if successful
        """
        new_volume = min(100, self.speaker_volume + step)
        return self.set_speaker_volume(new_volume)
    
    def decrease_volume(self, step: int = 10) -> bool:
        """
        Decrease speaker volume.
        
        Args:
            step: Volume decrement
            
        Returns:
            True if successful
        """
        new_volume = max(0, self.speaker_volume - step)
        return self.set_speaker_volume(new_volume)
    
    def route_to_bluetooth(self, device_address: str, max_retries: int = 10, 
                           retry_delay: float = 1.0) -> bool:
        """
        Route audio to Bluetooth device using PulseAudio.
        
        Args:
            device_address: Bluetooth device MAC address
            max_retries: Maximum number of retries to find the sink
            retry_delay: Delay between retries in seconds
            
        Returns:
            True if successful
        """
        address_normalized = device_address.replace(':', '_').lower()
        
        for attempt in range(max_retries):
            try:
                # Find Bluetooth sink
                result = subprocess.run(
                    ['pactl', 'list', 'short', 'sinks'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                bt_sink = None
                for line in result.stdout.split('\n'):
                    line_lower = line.lower()
                    # Check for bluez sink with matching address
                    if 'bluez' in line_lower and address_normalized in line_lower:
                        bt_sink = line.split()[1]
                        break
                    # Also check for bluetooth sink without bluez prefix
                    if 'bluetooth' in line_lower and address_normalized in line_lower:
                        bt_sink = line.split()[1]
                        break
                
                if bt_sink:
                    # Set as default sink
                    subprocess.run(
                        ['pactl', 'set-default-sink', bt_sink],
                        check=True,
                        capture_output=True
                    )
                    
                    logging.info(f"Audio routed to Bluetooth device: {device_address} (sink: {bt_sink})")
                    return True
                
                if attempt < max_retries - 1:
                    logging.debug(f"Bluetooth sink not found, retrying ({attempt + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                    
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to route audio to Bluetooth: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            except FileNotFoundError:
                logging.warning("pactl not found, using ALSA directly")
                return False
        
        logging.warning(f"Bluetooth sink not found for {device_address} after {max_retries} attempts")
        logging.info("Tip: Ensure pulseaudio-module-bluetooth is installed and PulseAudio is running")
        return False
    
    def set_profile_hfp(self, card_name: str) -> bool:
        """
        Set Bluetooth card to HFP/HSP profile.
        
        Args:
            card_name: PulseAudio card name
            
        Returns:
            True if successful
        """
        try:
            # Set card profile to headset_head_unit (HFP/HSP)
            subprocess.run(
                ['pactl', 'set-card-profile', card_name, 'headset_head_unit'],
                check=True,
                capture_output=True
            )
            
            logging.info(f"Set profile to headset_head_unit for {card_name}")
            return True
            
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to set HFP profile: {e}")
            return False
    
    def connect_sco(self, device_address: str) -> bool:
        """
        Connect SCO socket for Bluetooth voice audio.
        
        Args:
            device_address: Bluetooth device MAC address
            
        Returns:
            True if successful
        """
        try:
            # Create SCO socket
            self.sco_socket = socket.socket(
                socket.AF_BLUETOOTH,
                socket.SOCK_SEQPACKET,
                self.BTPROTO_SCO
            )
            
            # Set socket options for voice
            # SCO socket will be non-blocking for audio threading
            self.sco_socket.setblocking(False)
            
            # Connect to device
            self.sco_socket.connect((device_address,))
            
            logging.info(f"SCO socket connected to {device_address}")
            return True
            
        except (OSError, socket.error) as e:
            logging.error(f"Failed to connect SCO socket: {e}")
            if self.sco_socket:
                try:
                    self.sco_socket.close()
                except:
                    pass
                self.sco_socket = None
            return False
    
    def disconnect_sco(self) -> None:
        """Disconnect SCO socket."""
        if self.sco_socket:
            try:
                self.sco_socket.close()
            except:
                pass
            self.sco_socket = None
            logging.info("SCO socket disconnected")
    
    def start_audio_loop(self) -> bool:
        """
        Start audio capture/playback loop.
        
        Returns:
            True if started successfully
        """
        if self.audio_thread and self.audio_thread.is_alive():
            logging.warning("Audio loop already running")
            return False
        
        if not self.capture_device or not self.playback_device:
            logging.error("Audio devices not initialized")
            return False
        
        self._stop_event.clear()
        self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
        self.audio_thread.start()
        
        self.state = AudioState.ACTIVE_CALL
        logging.info("Audio loop started")
        return True
    
    def stop_audio_loop(self) -> None:
        """Stop audio capture/playback loop."""
        self._stop_event.set()
        if self.audio_thread:
            self.audio_thread.join(timeout=2.0)
            self.audio_thread = None
        
        self.state = AudioState.IDLE
        logging.info("Audio loop stopped")
    
    def _audio_loop(self) -> None:
        """Audio processing loop (runs in separate thread)."""
        logging.info("Audio loop thread started")
        
        while not self._stop_event.is_set():
            try:
                # Read from microphone
                with self._audio_lock:
                    if self.capture_device:
                        length, data = self.capture_device.read()
                    else:
                        length, data = 0, None
                
                if length > 0 and data:
                    # Apply preprocessing if enabled
                    processed_data = data
                    has_voice = True
                    
                    if self.preprocessor:
                        try:
                            processed_data = self.preprocessor.process_frame(data)
                            # Check voice activity for monitoring
                            has_voice = self.preprocessor._detect_voice_activity(
                                np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                            )
                        except Exception as e:
                            logging.error(f"Preprocessing error: {e}")
                            processed_data = data  # Fallback to unprocessed
                    
                    # Monitor quality if enabled
                    if self.monitor:
                        try:
                            self.monitor.record_capture_timestamp()
                            self.monitor.analyze_frame(processed_data, has_voice)
                            self.monitor.log_metrics(interval_frames=50)
                        except Exception as e:
                            logging.error(f"Monitoring error: {e}")
                    
                    # Send to SCO socket if connected (Bluetooth voice)
                    if self.sco_socket:
                        try:
                            self.sco_socket.send(processed_data)
                        except (socket.error, BlockingIOError):
                            pass  # Non-blocking socket, ignore if would block
                    
                    # Call callback with processed audio
                    if self.on_audio_data:
                        self.on_audio_data(processed_data)
                
                # Receive from SCO socket and play
                if self.sco_socket:
                    try:
                        incoming_data = self.sco_socket.recv(self.sco_mtu * 4)
                        if incoming_data:
                            # Update AEC reference before playing
                            if self.preprocessor:
                                self.preprocessor.update_speaker_signal(incoming_data)
                            
                            # Play received audio
                            with self._audio_lock:
                                if self.playback_device:
                                    self.playback_device.write(incoming_data)
                    except (socket.error, BlockingIOError):
                        pass  # Non-blocking, no data available
                
            except alsaaudio.ALSAAudioError as e:
                logging.error(f"Audio loop error: {e}")
                time.sleep(0.1)
            except Exception as e:
                logging.error(f"Unexpected error in audio loop: {e}")
                time.sleep(0.1)
        
        logging.info("Audio loop thread stopped")
    
    def play_audio(self, data: bytes) -> bool:
        """
        Play audio data to speaker.
        
        Args:
            data: Audio data bytes
            
        Returns:
            True if successful
        """
        try:
            if self.playback_device:
                self.playback_device.write(data)
                return True
            return False
        except alsaaudio.ALSAAudioError as e:
            logging.error(f"Failed to play audio: {e}")
            return False
    
    def get_quality_metrics(self) -> dict:
        """Get current audio quality metrics."""
        if self.monitor:
            return self.monitor.get_statistics()
        return {}
    
    def get_preprocessing_metrics(self) -> dict:
        """Get preprocessing statistics."""
        if self.preprocessor:
            return self.preprocessor.get_quality_metrics()
        return {}
    
    def set_codec_info(self, codec: str) -> None:
        """Update codec information for monitoring."""
        if self.monitor:
            self.monitor.set_codec_info(codec, self.sample_rate)
            logging.info(f"Codec set to {codec} @ {self.sample_rate}Hz")
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.stop_audio_loop()
        
        # Disconnect SCO
        self.disconnect_sco()
        
        with self._audio_lock:
            if self.capture_device:
                self.capture_device.close()
                self.capture_device = None
            
            if self.playback_device:
                self.playback_device.close()
                self.playback_device = None
        
        self.pulse.close()
        logging.info("AudioManager cleaned up")


if __name__ == "__main__":
    # Test audio manager
    logging.basicConfig(level=logging.INFO)
    
    audio = AudioManager()
    if audio.initialize():
        print("Audio devices initialized successfully")
        audio.set_speaker_volume(50)
        audio.set_microphone_volume(75)
        
        # Test audio loop for 5 seconds
        print("Testing audio loop for 5 seconds...")
        audio.start_audio_loop()
        time.sleep(5)
        audio.stop_audio_loop()
        
        audio.cleanup()
