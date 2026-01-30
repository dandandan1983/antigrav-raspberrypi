#!/usr/bin/env python3
"""
Configuration Module for RPi Hands-Free Headset

This module handles loading and managing configuration from config.ini file.
It provides easy access to all configuration parameters used throughout the application.
"""

import configparser
import os
import logging
from pathlib import Path
from typing import Dict, Any


class Config:
    """Configuration manager for the hands-free headset application."""
    
    def __init__(self, config_file: str = "config.ini"):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file (default: config.ini)
        """
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load()
    
    def load(self) -> None:
        """Load configuration from file."""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        
        self.config.read(self.config_file)
        logging.info(f"Configuration loaded from {self.config_file}")
    
    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            section: Configuration section name
            key: Configuration key name
            fallback: Default value if key not found
            
        Returns:
            Configuration value
        """
        return self.config.get(section, key, fallback=fallback)
    
    def get_int(self, section: str, key: str, fallback: int = 0) -> int:
        """Get integer configuration value."""
        return self.config.getint(section, key, fallback=fallback)
    
    def get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        """Get float configuration value."""
        return self.config.getfloat(section, key, fallback=fallback)
    
    def get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        """Get boolean configuration value."""
        return self.config.getboolean(section, key, fallback=fallback)
    
    # Bluetooth configuration properties
    @property
    def bt_device_name(self) -> str:
        """Bluetooth device name."""
        return self.get('bluetooth', 'device_name', 'RPi Hands-Free')
    
    @property
    def bt_device_class(self) -> str:
        """Bluetooth device class."""
        return self.get('bluetooth', 'device_class', '0x200404')
    
    @property
    def bt_discoverable(self) -> bool:
        """Whether device should be discoverable."""
        return self.get_bool('bluetooth', 'discoverable', True)
    
    @property
    def bt_auto_reconnect(self) -> bool:
        """Whether to auto-reconnect to last known device."""
        return self.get_bool('bluetooth', 'auto_reconnect', True)
    
    @property
    def bt_pin_code(self) -> str:
        """Bluetooth pairing PIN code."""
        return self.get('bluetooth', 'pin_code', '0000')
    
    # Audio configuration properties
    @property
    def audio_sample_rate(self) -> int:
        """Audio sample rate in Hz."""
        return self.get_int('audio', 'sample_rate', 16000)
    
    @property
    def audio_channels(self) -> int:
        """Number of audio channels."""
        return self.get_int('audio', 'channels', 1)
    
    @property
    def audio_format(self) -> str:
        """Audio format."""
        return self.get('audio', 'format', 'S16_LE')
    
    @property
    def audio_buffer_size(self) -> int:
        """Audio buffer size in frames."""
        return self.get_int('audio', 'buffer_size', 2048)
    
    @property
    def audio_sco_mtu(self) -> int:
        """SCO MTU (Maximum Transmission Unit)."""
        return self.get_int('audio', 'sco_mtu', 48)
    
    @property
    def audio_capture_device(self) -> str:
        """Audio capture device name (PulseAudio)."""
        return self.get("audio", "capture_device", fallback="default")
    
    @property
    def audio_playback_device(self) -> str:
        """Audio playback device name (PulseAudio)."""
        return self.get("audio", "playback_device", fallback="default")
    
    @property
    def audio_aec_tail_ms(self) -> int:
        """Echo cancellation tail length in milliseconds."""
        return self.get_int('audio', 'aec_tail_length', 200)
    
    # Reconnect configuration
    @property
    def bt_reconnect_attempts(self) -> int:
        """Number of reconnection attempts."""
        return self.get_int('bluetooth', 'reconnect_attempts', 5)
    
    @property
    def bt_reconnect_delay(self) -> float:
        """Initial delay between reconnection attempts in seconds."""
        return self.get_float('bluetooth', 'reconnect_delay', 2.0)
    
    @property
    def bt_reconnect_max_delay(self) -> float:
        """Maximum delay between reconnection attempts (exponential backoff)."""
        return self.get_float('bluetooth', 'reconnect_max_delay', 30.0)
    
    # Audio Quality Enhancement properties
    @property
    def audio_enable_wideband(self) -> bool:
        """Enable Wide-Band Speech (mSBC codec)."""
        return self.get_bool('audio', 'enable_wideband', True)
    
    @property
    def audio_enable_preprocessing(self) -> bool:
        """Enable audio preprocessing pipeline."""
        return self.get_bool('audio', 'enable_preprocessing', True)
    
    @property
    def audio_noise_reduction_level(self) -> int:
        """Noise reduction level (0-3)."""
        return self.get_int('audio', 'noise_reduction_level', 2)
    
    @property
    def audio_enable_aec(self) -> bool:
        """Enable echo cancellation."""
        return self.get_bool('audio', 'enable_aec', True)
    
    @property
    def audio_enable_agc(self) -> bool:
        """Enable automatic gain control."""
        return self.get_bool('audio', 'enable_agc', True)
    
    @property
    def audio_agc_target_level(self) -> float:
        """AGC target level in dB."""
        return self.get_float('audio', 'agc_target_level', -6.0)
    
    @property
    def audio_enable_highpass(self) -> bool:
        """Enable high-pass filter."""
        return self.get_bool('audio', 'enable_highpass', True)
    
    @property
    def audio_highpass_cutoff(self) -> float:
        """High-pass filter cutoff frequency in Hz."""
        return self.get_float('audio', 'highpass_cutoff', 80.0)
    
    @property
    def audio_enable_quality_monitoring(self) -> bool:
        """Enable quality monitoring."""
        return self.get_bool('audio', 'enable_quality_monitoring', True)
    
    # GPIO configuration properties
    @property
    def gpio_button_answer(self) -> int:
        """GPIO pin for answer/hangup button."""
        return self.get_int('gpio', 'button_answer', 17)
    
    @property
    def gpio_button_reject(self) -> int:
        """GPIO pin for reject button."""
        return self.get_int('gpio', 'button_reject', 27)
    
    @property
    def gpio_button_vol_up(self) -> int:
        """GPIO pin for volume up button."""
        return self.get_int('gpio', 'button_vol_up', 22)
    
    @property
    def gpio_button_vol_down(self) -> int:
        """GPIO pin for volume down button."""
        return self.get_int('gpio', 'button_vol_down', 23)
    
    @property
    def gpio_led_status(self) -> int:
        """GPIO pin for status LED."""
        return self.get_int('gpio', 'led_status', 24)
    
    @property
    def gpio_led_call(self) -> int:
        """GPIO pin for call LED."""
        return self.get_int('gpio', 'led_call', 25)
    
    @property
    def gpio_debounce_time(self) -> int:
        """Button debounce time in milliseconds."""
        return self.get_int('gpio', 'debounce_time', 200)
    
    # Misc configuration properties
    @property
    def log_level(self) -> str:
        """Logging level."""
        return self.get('misc', 'log_level', 'INFO')
    
    @property
    def log_file(self) -> str:
        """Log file path."""
        return self.get('misc', 'log_file', '/var/log/rpi-handsfree.log')
    
    @property
    def log_to_console(self) -> bool:
        """Whether to log to console."""
        return self.get_bool('misc', 'log_to_console', True)
    
    def __str__(self) -> str:
        """String representation of configuration."""
        return f"Config(file={self.config_file})"


# Global configuration instance
_config_instance = None


def get_config(config_file: str = "config.ini") -> Config:
    """
    Get global configuration instance.
    
    Args:
        config_file: Path to configuration file
        
    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


if __name__ == "__main__":
    # Test configuration loading
    config = get_config()
    print(f"Device Name: {config.bt_device_name}")
    print(f"Sample Rate: {config.audio_sample_rate}")
    print(f"Log Level: {config.log_level}")
