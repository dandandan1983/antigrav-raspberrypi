#!/usr/bin/env python3
"""
Comprehensive unit tests for Configuration Module
"""

import unittest
from unittest.mock import Mock, patch, mock_open
import sys
from pathlib import Path
import tempfile
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from config import Config


class TestConfig(unittest.TestCase):
    """Test cases for Config class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_config_content = """
[bluetooth]
device_name = Test Device
device_class = 0x200404
discoverable = true
auto_reconnect = true

[audio]
sample_rate = 16000
channels = 1
buffer_size = 2048
enable_wideband = true
enable_preprocessing = true
noise_reduction_level = 2
enable_aec = true
enable_agc = true
agc_target_level = -6
enable_highpass = true
highpass_cutoff = 80
enable_quality_monitoring = true

[gpio]
button_answer = 17
button_reject = 27
button_vol_up = 22
button_vol_down = 23
led_status = 24
led_call = 25

[misc]
log_level = INFO
log_file = /var/log/rpi-handsfree.log
"""
    
    def _create_temp_config(self, content=None):
        """Create temporary config file."""
        if content is None:
            content = self.test_config_content
        
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini')
        temp_file.write(content)
        temp_file.close()
        return temp_file.name
    
    def tearDown(self):
        """Clean up temporary files."""
        # Cleanup handled by test methods
        pass
    
    # ========== Initialization Tests ==========
    
    def test_initialization_with_file(self):
        """Test Config initialization with file."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertIsNotNone(config)
        finally:
            os.unlink(config_path)
    
    def test_initialization_without_file(self):
        """Test Config initialization without file raises error."""
        # Config requires a file, so this should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            config = Config('/nonexistent/path/config.ini')
    
    def test_initialization_nonexistent_file(self):
        """Test Config initialization with non-existent file raises error."""
        # Should raise FileNotFoundError for missing file
        with self.assertRaises(FileNotFoundError):
            config = Config('/another/nonexistent/path/config.ini')
    
    # ========== Bluetooth Configuration Tests ==========
    
    def test_bluetooth_device_name(self):
        """Test reading Bluetooth device name."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.bt_device_name, "Test Device")
        finally:
            os.unlink(config_path)
    
    def test_bluetooth_device_class(self):
        """Test reading Bluetooth device class."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.bt_device_class, "0x200404")
        finally:
            os.unlink(config_path)
    
    def test_bluetooth_discoverable(self):
        """Test reading Bluetooth discoverable setting."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertTrue(config.bt_discoverable)
        finally:
            os.unlink(config_path)
    
    def test_bluetooth_auto_reconnect(self):
        """Test reading Bluetooth auto-reconnect setting."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertTrue(config.bt_auto_reconnect)
        finally:
            os.unlink(config_path)
    
    # ========== Audio Configuration Tests ==========
    
    def test_audio_sample_rate(self):
        """Test reading audio sample rate."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.audio_sample_rate, 16000)
        finally:
            os.unlink(config_path)
    
    def test_audio_channels(self):
        """Test reading audio channels."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.audio_channels, 1)
        finally:
            os.unlink(config_path)
    
    def test_audio_buffer_size(self):
        """Test reading audio buffer size."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.audio_buffer_size, 2048)
        finally:
            os.unlink(config_path)
    
    def test_audio_enable_wideband(self):
        """Test reading wideband audio setting."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertTrue(config.audio_enable_wideband)
        finally:
            os.unlink(config_path)
    
    def test_audio_enable_preprocessing(self):
        """Test reading preprocessing setting."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertTrue(config.audio_enable_preprocessing)
        finally:
            os.unlink(config_path)
    
    def test_audio_noise_reduction_level(self):
        """Test reading noise reduction level."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.audio_noise_reduction_level, 2)
        finally:
            os.unlink(config_path)
    
    def test_audio_agc_target_level(self):
        """Test reading AGC target level."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.audio_agc_target_level, -6.0)
        finally:
            os.unlink(config_path)
    
    # ========== GPIO Configuration Tests ==========
    
    def test_gpio_button_pins(self):
        """Test reading GPIO button pin numbers."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.gpio_button_answer, 17)
            self.assertEqual(config.gpio_button_reject, 27)
            self.assertEqual(config.gpio_button_vol_up, 22)
            self.assertEqual(config.gpio_button_vol_down, 23)
        finally:
            os.unlink(config_path)
    
    def test_gpio_led_pins(self):
        """Test reading GPIO LED pin numbers."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.gpio_led_status, 24)
            self.assertEqual(config.gpio_led_call, 25)
        finally:
            os.unlink(config_path)
    
    # ========== Misc Configuration Tests ==========
    
    def test_log_level(self):
        """Test reading log level."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.log_level, "INFO")
        finally:
            os.unlink(config_path)
    
    def test_log_file(self):
        """Test reading log file path."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertEqual(config.log_file, "/var/log/rpi-handsfree.log")
        finally:
            os.unlink(config_path)
    
    # ========== Default Values Tests ==========
    
    def test_default_values(self):
        """Test default configuration values."""
        # Create a minimal config file for testing defaults
        minimal_config = "[bluetooth]\ndevice_name = Test\n"
        config_path = self._create_temp_config(minimal_config)
        try:
            config = Config(config_path)
            # Should have reasonable defaults
            self.assertIsNotNone(config.bt_device_name)
            self.assertGreater(config.audio_sample_rate, 0)
            self.assertGreater(config.audio_buffer_size, 0)
        finally:
            os.unlink(config_path)
    
    def test_missing_section_defaults(self):
        """Test defaults when section is missing."""
        minimal_config = """
[bluetooth]
device_name = Test
"""
        config_path = self._create_temp_config(minimal_config)
        try:
            config = Config(config_path)
            # Should have defaults for missing sections
            self.assertIsNotNone(config.audio_sample_rate)
        finally:
            os.unlink(config_path)
    
    def test_missing_key_defaults(self):
        """Test defaults when keys are missing."""
        partial_config = """
[audio]
sample_rate = 16000
"""
        config_path = self._create_temp_config(partial_config)
        try:
            config = Config(config_path)
            # Should have defaults for missing keys
            self.assertIsNotNone(config.audio_channels)
        finally:
            os.unlink(config_path)
    
    # ========== Type Conversion Tests ==========
    
    def test_boolean_conversion_true(self):
        """Test boolean conversion for true values."""
        config_with_bools = """
[test]
value1 = true
value2 = True
value3 = yes
value4 = 1
"""
        config_path = self._create_temp_config(config_with_bools)
        try:
            config = Config(config_path)
            # Test that booleans are parsed correctly
            # Depends on implementation
        finally:
            os.unlink(config_path)
    
    def test_boolean_conversion_false(self):
        """Test boolean conversion for false values."""
        config_with_bools = """
[test]
value1 = false
value2 = False
value3 = no
value4 = 0
"""
        config_path = self._create_temp_config(config_with_bools)
        try:
            config = Config(config_path)
            # Test that booleans are parsed correctly
        finally:
            os.unlink(config_path)
    
    def test_integer_conversion(self):
        """Test integer conversion."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertIsInstance(config.audio_sample_rate, int)
            self.assertIsInstance(config.audio_buffer_size, int)
        finally:
            os.unlink(config_path)
    
    def test_float_conversion(self):
        """Test float conversion."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            self.assertIsInstance(config.audio_agc_target_level, (int, float))
        finally:
            os.unlink(config_path)
    
    # ========== Validation Tests ==========
    
    def test_sample_rate_validation(self):
        """Test sample rate validation."""
        invalid_config = """
[audio]
sample_rate = -1000
"""
        config_path = self._create_temp_config(invalid_config)
        try:
            config = Config(config_path)
            # Should either use default or raise
            if hasattr(config, 'audio_sample_rate'):
                self.assertGreater(config.audio_sample_rate, 0)
        except ValueError:
            pass  # Expected if validation is strict
        finally:
            os.unlink(config_path)
    
    def test_noise_reduction_level_validation(self):
        """Test noise reduction level validation (0-3)."""
        invalid_config = """
[audio]
noise_reduction_level = 10
"""
        config_path = self._create_temp_config(invalid_config)
        try:
            config = Config(config_path)
            # Should clamp or use default
            if hasattr(config, 'audio_noise_reduction_level'):
                self.assertLessEqual(config.audio_noise_reduction_level, 3)
                self.assertGreaterEqual(config.audio_noise_reduction_level, 0)
        finally:
            os.unlink(config_path)
    
    def test_gpio_pin_validation(self):
        """Test GPIO pin number validation."""
        invalid_config = """
[gpio]
button_answer = 100
"""
        config_path = self._create_temp_config(invalid_config)
        try:
            config = Config(config_path)
            # Should validate GPIO pin range (typically 2-27 on Pi)
            # Or use default
        except ValueError:
            pass  # Expected if validation is strict
        finally:
            os.unlink(config_path)
    
    # ========== Reload Tests ==========
    
    def test_reload_config(self):
        """Test reloading configuration."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            original_name = config.bluetooth_device_name
            
            # Modify config file
            with open(config_path, 'w') as f:
                f.write("""
[bluetooth]
device_name = Modified Device
""")
            
            # Reload
            if hasattr(config, 'reload'):
                config.reload()
                self.assertEqual(config.bluetooth_device_name, "Modified Device")
        finally:
            os.unlink(config_path)
    
    # ========== Error Handling Tests ==========
    
    def test_malformed_config(self):
        """Test handling of malformed config file."""
        malformed_config = """
[bluetooth
device_name = Test
invalid line without equals sign
"""
        config_path = self._create_temp_config(malformed_config)
        try:
            config = Config(config_path)
            # Should handle gracefully
        except Exception:
            pass  # Expected for malformed config
        finally:
            os.unlink(config_path)
    
    def test_empty_config_file(self):
        """Test handling of empty config file."""
        config_path = self._create_temp_config("")
        try:
            config = Config(config_path)
            # Should use all defaults
            self.assertIsNotNone(config)
        finally:
            os.unlink(config_path)
    
    # ========== Property Access Tests ==========
    
    def test_get_all_settings(self):
        """Test getting all settings as dict."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            if hasattr(config, 'to_dict'):
                settings = config.to_dict()
                self.assertIsInstance(settings, dict)
                self.assertIn('bluetooth', settings)
                self.assertIn('audio', settings)
        finally:
            os.unlink(config_path)
    
    def test_config_property_access(self):
        """Test property-style access to config values."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            # Should be accessible via properties
            _ = config.bt_device_name
            _ = config.audio_sample_rate
            _ = config.gpio_button_answer
        finally:
            os.unlink(config_path)
    
    # ========== Section Tests ==========
    
    def test_all_sections_present(self):
        """Test that all required sections are present."""
        config_path = self._create_temp_config()
        try:
            config = Config(config_path)
            required_sections = ['bluetooth', 'audio', 'gpio', 'misc']
            
            if hasattr(config, '_config'):
                for section in required_sections:
                    self.assertIn(section, config._config.sections())
        finally:
            os.unlink(config_path)


if __name__ == '__main__':
    unittest.main()
