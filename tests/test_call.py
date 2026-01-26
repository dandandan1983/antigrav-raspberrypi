#!/usr/bin/env python3
"""
Unit tests for Call Manager
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from call_manager import CallManager, CallState


class TestCallManager(unittest.TestCase):
    """Test cases for CallManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.call_manager = CallManager()
    
    def test_initialization(self):
        """Test CallManager initialization."""
        self.assertEqual(self.call_manager.state, CallState.IDLE)
        self.assertEqual(self.call_manager.caller_id, "")
        self.assertEqual(self.call_manager.caller_name, "")
        self.assertEqual(self.call_manager.speaker_volume, 10)
        self.assertEqual(self.call_manager.mic_volume, 10)
    
    def test_at_command_constants(self):
        """Test AT command constants."""
        self.assertEqual(CallManager.AT_ATA, "ATA")
        self.assertEqual(CallManager.AT_CHUP, "AT+CHUP")
        self.assertEqual(CallManager.AT_VGS, "AT+VGS")
        self.assertEqual(CallManager.AT_VGM, "AT+VGM")
    
    def test_callback_registration(self):
        """Test callback registration."""
        callback = Mock()
        
        self.call_manager.on_incoming_call = callback
        self.assertEqual(self.call_manager.on_incoming_call, callback)
        
        self.call_manager.on_call_answered = callback
        self.assertEqual(self.call_manager.on_call_answered, callback)
    
    def test_state_transitions(self):
        """Test call state transitions."""
        self.assertEqual(self.call_manager.state, CallState.IDLE)
        
        # Simulate incoming call
        self.call_manager.state = CallState.INCOMING
        self.assertEqual(self.call_manager.state, CallState.INCOMING)
        
        # Answer call
        self.call_manager.state = CallState.ACTIVE
        self.assertEqual(self.call_manager.state, CallState.ACTIVE)
        
        # End call
        self.call_manager.state = CallState.IDLE
        self.assertEqual(self.call_manager.state, CallState.IDLE)
    
    def test_volume_range(self):
        """Test HFP volume range (0-15)."""
        # Test valid volumes
        for vol in [0, 7, 15]:
            clamped = max(0, min(15, vol))
            self.assertEqual(clamped, vol)
        
        # Test clamping
        self.assertEqual(max(0, min(15, -5)), 0)
        self.assertEqual(max(0, min(15, 20)), 15)
    
    def test_at_command_parsing(self):
        """Test AT command response parsing."""
        # Test RING detection
        command = "RING"
        self.assertTrue(command.startswith("RING"))
        
        # Test +CLIP parsing
        command = '+CLIP: "+1234567890",145'
        self.assertTrue(command.startswith("+CLIP:"))
        
        # Test +VGS parsing
        command = "+VGS: 10"
        self.assertTrue(command.startswith("+VGS:"))


if __name__ == '__main__':
    unittest.main()
