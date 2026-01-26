#!/usr/bin/env python3
"""
Unit tests for Bluetooth Manager
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from bluetooth_manager import BluetoothManager, ConnectionState


class TestBluetoothManager(unittest.TestCase):
    """Test cases for BluetoothManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.bt_manager = BluetoothManager(
            device_name="Test Device",
            device_class="0x200404"
        )
    
    def test_initialization(self):
        """Test BluetoothManager initialization."""
        self.assertEqual(self.bt_manager.device_name, "Test Device")
        self.assertEqual(self.bt_manager.device_class, "0x200404")
        self.assertEqual(self.bt_manager.state, ConnectionState.DISCONNECTED)
        self.assertIsNone(self.bt_manager.connected_device)
    
    def test_uuid_constants(self):
        """Test Bluetooth UUID constants."""
        self.assertEqual(
            BluetoothManager.HSP_AG_UUID,
            "00001112-0000-1000-8000-00805f9b34fb"
        )
        self.assertEqual(
            BluetoothManager.HFP_AG_UUID,
            "0000111f-0000-1000-8000-00805f9b34fb"
        )
    
    @patch('bluetooth_manager.dbus.SystemBus')
    def test_initialize_success(self, mock_bus):
        """Test successful Bluetooth initialization."""
        # Mock D-Bus objects
        mock_bus_instance = MagicMock()
        mock_bus.return_value = mock_bus_instance
        
        # This would require extensive mocking of D-Bus
        # Skipping full integration test for unit tests
        pass
    
    def test_callback_registration(self):
        """Test callback registration."""
        callback = Mock()
        
        self.bt_manager.on_connected = callback
        self.assertEqual(self.bt_manager.on_connected, callback)
        
        self.bt_manager.on_disconnected = callback
        self.assertEqual(self.bt_manager.on_disconnected, callback)
    
    def test_state_transitions(self):
        """Test connection state transitions."""
        self.assertEqual(self.bt_manager.state, ConnectionState.DISCONNECTED)
        
        # Simulate state change
        self.bt_manager.state = ConnectionState.CONNECTING
        self.assertEqual(self.bt_manager.state, ConnectionState.CONNECTING)
        
        self.bt_manager.state = ConnectionState.CONNECTED
        self.assertEqual(self.bt_manager.state, ConnectionState.CONNECTED)


if __name__ == '__main__':
    unittest.main()
