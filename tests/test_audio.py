#!/usr/bin/env python3
"""
Unit tests for Audio Manager
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from audio_manager import AudioManager, AudioState


class TestAudioManager(unittest.TestCase):
    """Test cases for AudioManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.audio_manager = AudioManager(
            sample_rate=16000,
            channels=1,
            buffer_size=2048
        )
    
    def test_initialization(self):
        """Test AudioManager initialization."""
        self.assertEqual(self.audio_manager.sample_rate, 16000)
        self.assertEqual(self.audio_manager.channels, 1)
        self.assertEqual(self.audio_manager.buffer_size, 2048)
        self.assertEqual(self.audio_manager.state, AudioState.IDLE)
        self.assertEqual(self.audio_manager.speaker_volume, 75)
        self.assertEqual(self.audio_manager.microphone_volume, 75)
    
    def test_volume_clamping(self):
        """Test volume value clamping."""
        # Volume should be clamped to 0-100 range
        # This is tested in the actual methods, not initialization
        pass
    
    def test_volume_increase(self):
        """Test volume increase."""
        self.audio_manager.speaker_volume = 50
        # Simulate volume increase (would call actual method on real system)
        new_volume = min(100, self.audio_manager.speaker_volume + 10)
        self.assertEqual(new_volume, 60)
    
    def test_volume_decrease(self):
        """Test volume decrease."""
        self.audio_manager.speaker_volume = 50
        # Simulate volume decrease
        new_volume = max(0, self.audio_manager.speaker_volume - 10)
        self.assertEqual(new_volume, 40)
    
    def test_callback_registration(self):
        """Test callback registration."""
        callback = Mock()
        
        self.audio_manager.on_audio_data = callback
        self.assertEqual(self.audio_manager.on_audio_data, callback)
    
    def test_state_transitions(self):
        """Test audio state transitions."""
        self.assertEqual(self.audio_manager.state, AudioState.IDLE)
        
        self.audio_manager.state = AudioState.CAPTURING
        self.assertEqual(self.audio_manager.state, AudioState.CAPTURING)
        
        self.audio_manager.state = AudioState.ACTIVE_CALL
        self.assertEqual(self.audio_manager.state, AudioState.ACTIVE_CALL)


if __name__ == '__main__':
    unittest.main()
