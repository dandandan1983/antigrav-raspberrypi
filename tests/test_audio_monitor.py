#!/usr/bin/env python3
"""
Comprehensive unit tests for Audio Monitor Module
"""

import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path
import numpy as np
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from audio_monitor import AudioMonitor, AudioQualityMetrics


class TestAudioMonitor(unittest.TestCase):
    """Test cases for AudioMonitor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.monitor = AudioMonitor(sample_rate=16000, window_size=100)
        self.sample_rate = 16000
        self.frame_duration = 0.02  # 20ms
        self.frame_size = int(self.sample_rate * self.frame_duration)
    
    def _generate_test_audio(self, frequency=440, duration=0.02, amplitude=0.5):
        """Generate test audio signal."""
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        audio = amplitude * np.sin(2 * np.pi * frequency * t)
        return audio.astype(np.float32)
    
    def _audio_to_bytes(self, audio):
        """Convert float audio to 16-bit PCM bytes."""
        audio_int16 = (audio * 32767).astype(np.int16)
        return audio_int16.tobytes()
    
    # ========== Initialization Tests ==========
    
    def test_initialization(self):
        """Test AudioMonitor initialization."""
        self.assertEqual(self.monitor.sample_rate, 16000)
        self.assertEqual(self.monitor.window_size, 100)
        self.assertEqual(self.monitor.frames_analyzed, 0)
        self.assertEqual(self.monitor.codec, "unknown")
    
    def test_initialization_custom_params(self):
        """Test initialization with custom parameters."""
        monitor = AudioMonitor(sample_rate=8000, window_size=50)
        self.assertEqual(monitor.sample_rate, 8000)
        self.assertEqual(monitor.window_size, 50)
    
    # ========== Frame Analysis Tests ==========
    
    def test_analyze_frame_silence(self):
        """Test analyzing silent frame."""
        silence = np.zeros(self.frame_size, dtype=np.float32)
        silence_bytes = self._audio_to_bytes(silence)
        
        self.monitor.analyze_frame(silence_bytes, has_voice=False)
        
        self.assertEqual(self.monitor.frames_analyzed, 1)
        metrics = self.monitor.get_current_metrics()
        self.assertLess(metrics.rms_level_db, -40)  # Very quiet
    
    def test_analyze_frame_signal(self):
        """Test analyzing signal frame."""
        signal = self._generate_test_audio(frequency=1000, amplitude=0.5)
        signal_bytes = self._audio_to_bytes(signal)
        
        self.monitor.analyze_frame(signal_bytes, has_voice=True)
        
        self.assertEqual(self.monitor.frames_analyzed, 1)
        metrics = self.monitor.get_current_metrics()
        self.assertGreater(metrics.rms_level_db, -10)  # Should have signal
    
    def test_analyze_multiple_frames(self):
        """Test analyzing multiple frames."""
        for i in range(10):
            signal = self._generate_test_audio(frequency=440, amplitude=0.3)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes, has_voice=True)
        
        self.assertEqual(self.monitor.frames_analyzed, 10)
    
    # ========== RMS Level Tests ==========
    
    def test_rms_level_calculation(self):
        """Test RMS level calculation."""
        # Known amplitude signal
        amplitude = 0.5
        signal = self._generate_test_audio(frequency=1000, amplitude=amplitude)
        signal_bytes = self._audio_to_bytes(signal)
        
        self.monitor.analyze_frame(signal_bytes)
        metrics = self.monitor.get_current_metrics()
        
        # RMS of sine wave = amplitude / sqrt(2)
        expected_rms = amplitude / np.sqrt(2)
        expected_db = 20 * np.log10(expected_rms)
        
        # Allow some tolerance
        self.assertAlmostEqual(metrics.rms_level_db, expected_db, delta=2)
    
    def test_peak_level_calculation(self):
        """Test peak level calculation."""
        amplitude = 0.7
        signal = self._generate_test_audio(frequency=1000, amplitude=amplitude)
        signal_bytes = self._audio_to_bytes(signal)
        
        self.monitor.analyze_frame(signal_bytes)
        metrics = self.monitor.get_current_metrics()
        
        expected_peak_db = 20 * np.log10(amplitude)
        
        self.assertAlmostEqual(metrics.peak_level_db, expected_peak_db, delta=1)
    
    # ========== SNR Tests ==========
    
    def test_snr_calculation_clean_signal(self):
        """Test SNR calculation with clean signal."""
        # First, establish noise floor with silence
        for _ in range(30):
            silence = np.zeros(self.frame_size, dtype=np.float32)
            silence_bytes = self._audio_to_bytes(silence)
            self.monitor.analyze_frame(silence_bytes, has_voice=False)
        
        # Then process signal
        for _ in range(10):
            signal = self._generate_test_audio(frequency=1000, amplitude=0.5)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes, has_voice=True)
        
        metrics = self.monitor.get_current_metrics()
        
        # Clean signal should have high SNR
        self.assertGreater(metrics.snr_db, 20)
    
    def test_snr_calculation_noisy_signal(self):
        """Test SNR calculation with noisy signal."""
        # Establish noise floor
        noise_level = 0.1
        for _ in range(30):
            noise = np.random.normal(0, noise_level, self.frame_size).astype(np.float32)
            noise_bytes = self._audio_to_bytes(noise)
            self.monitor.analyze_frame(noise_bytes, has_voice=False)
        
        # Process noisy signal
        for _ in range(10):
            signal = self._generate_test_audio(frequency=1000, amplitude=0.3)
            noise = np.random.normal(0, noise_level, self.frame_size).astype(np.float32)
            noisy_signal = signal + noise
            noisy_bytes = self._audio_to_bytes(noisy_signal)
            self.monitor.analyze_frame(noisy_bytes, has_voice=True)
        
        metrics = self.monitor.get_current_metrics()
        
        # Noisy signal should have lower SNR
        self.assertLess(metrics.snr_db, 20)
        self.assertGreater(metrics.snr_db, 0)
    
    # ========== Clipping Detection Tests ==========
    
    def test_clipping_detection_no_clip(self):
        """Test clipping detection with no clipping."""
        signal = self._generate_test_audio(frequency=1000, amplitude=0.5)
        signal_bytes = self._audio_to_bytes(signal)
        
        self.monitor.analyze_frame(signal_bytes)
        metrics = self.monitor.get_current_metrics()
        
        self.assertEqual(metrics.clipping_percent, 0.0)
    
    def test_clipping_detection_with_clip(self):
        """Test clipping detection with clipping."""
        # Create signal that clips
        signal = self._generate_test_audio(frequency=1000, amplitude=1.5)
        signal = np.clip(signal, -1.0, 1.0)  # Clip to valid range
        signal_bytes = self._audio_to_bytes(signal)
        
        self.monitor.analyze_frame(signal_bytes)
        metrics = self.monitor.get_current_metrics()
        
        # Should detect clipping
        self.assertGreater(metrics.clipping_percent, 0)
    
    def test_clipping_percentage_accuracy(self):
        """Test clipping percentage accuracy."""
        # Create signal with known clipping percentage
        signal = np.ones(self.frame_size, dtype=np.float32) * 0.5
        # Make 10% of samples clip
        num_clip = int(self.frame_size * 0.1)
        signal[:num_clip] = 1.0
        signal_bytes = self._audio_to_bytes(signal)
        
        self.monitor.analyze_frame(signal_bytes)
        metrics = self.monitor.get_current_metrics()
        
        # Should detect approximately 10% clipping
        self.assertAlmostEqual(metrics.clipping_percent, 10.0, delta=2)
    
    # ========== Voice Activity Tests ==========
    
    def test_voice_activity_tracking(self):
        """Test voice activity percentage tracking."""
        # Process 10 frames with voice
        for _ in range(10):
            signal = self._generate_test_audio(frequency=440, amplitude=0.3)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes, has_voice=True)
        
        # Process 10 frames without voice
        for _ in range(10):
            silence = np.zeros(self.frame_size, dtype=np.float32)
            silence_bytes = self._audio_to_bytes(silence)
            self.monitor.analyze_frame(silence_bytes, has_voice=False)
        
        metrics = self.monitor.get_current_metrics()
        
        # Should be 50% voice activity
        self.assertAlmostEqual(metrics.voice_activity_percent, 50.0, delta=5)
    
    # ========== Codec Info Tests ==========
    
    def test_set_codec_info(self):
        """Test setting codec information."""
        self.monitor.set_codec_info("mSBC", 16000)
        
        metrics = self.monitor.get_current_metrics()
        self.assertEqual(metrics.codec, "mSBC")
        self.assertEqual(metrics.sample_rate, 16000)
    
    def test_set_codec_info_cvsd(self):
        """Test setting CVSD codec."""
        self.monitor.set_codec_info("CVSD", 8000)
        
        metrics = self.monitor.get_current_metrics()
        self.assertEqual(metrics.codec, "CVSD")
        self.assertEqual(metrics.sample_rate, 8000)
    
    # ========== Latency Tests ==========
    
    def test_latency_estimation(self):
        """Test latency estimation."""
        self.monitor.record_capture_timestamp()
        time.sleep(0.05)  # 50ms delay
        self.monitor.record_output_timestamp()
        
        latency = self.monitor.estimate_latency()
        
        # Should be approximately 50ms
        self.assertGreater(latency, 40)
        self.assertLess(latency, 60)
    
    def test_latency_in_metrics(self):
        """Test latency included in metrics."""
        self.monitor.record_capture_timestamp()
        time.sleep(0.1)
        self.monitor.record_output_timestamp()
        
        metrics = self.monitor.get_current_metrics()
        
        self.assertGreater(metrics.latency_ms, 90)
        self.assertLess(metrics.latency_ms, 110)
    
    # ========== Statistics Tests ==========
    
    def test_get_statistics(self):
        """Test getting overall statistics."""
        # Process some frames
        for i in range(20):
            signal = self._generate_test_audio(frequency=440, amplitude=0.3)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes, has_voice=i % 2 == 0)
        
        stats = self.monitor.get_statistics()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_frames', stats)
        self.assertIn('avg_rms_db', stats)
        self.assertIn('avg_snr_db', stats)
        self.assertIn('avg_clipping_percent', stats)
        self.assertIn('voice_activity_percent', stats)
        
        self.assertEqual(stats['total_frames'], 20)
    
    def test_statistics_averaging(self):
        """Test statistics averaging across frames."""
        # Process frames with different levels
        for i in range(10):
            amplitude = 0.1 + (i * 0.05)  # Varying amplitude
            signal = self._generate_test_audio(frequency=1000, amplitude=amplitude)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes)
        
        stats = self.monitor.get_statistics()
        
        # Average should be somewhere in middle
        self.assertGreater(stats['avg_rms_db'], -40)
        self.assertLess(stats['avg_rms_db'], 0)
    
    # ========== Quality Assessment Tests ==========
    
    def test_quality_acceptable_good_signal(self):
        """Test quality assessment with good signal."""
        # Establish baseline
        for _ in range(30):
            silence = np.zeros(self.frame_size, dtype=np.float32)
            silence_bytes = self._audio_to_bytes(silence)
            self.monitor.analyze_frame(silence_bytes, has_voice=False)
        
        # Process good quality signal
        self.monitor.set_codec_info("mSBC", 16000)
        for _ in range(30):
            signal = self._generate_test_audio(frequency=1000, amplitude=0.3)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes, has_voice=True)
        
        acceptable, reason = self.monitor.is_quality_acceptable()
        
        self.assertTrue(acceptable)
        self.assertIn("Good", reason)
    
    def test_quality_unacceptable_high_clipping(self):
        """Test quality assessment with high clipping."""
        # Process clipping signal
        self.monitor.set_codec_info("mSBC", 16000)
        for _ in range(50):
            signal = np.ones(self.frame_size, dtype=np.float32) * 1.0
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes)
        
        acceptable, reason = self.monitor.is_quality_acceptable()
        
        self.assertFalse(acceptable)
        self.assertIn("clipping", reason.lower())
    
    def test_quality_unacceptable_too_quiet(self):
        """Test quality assessment with too quiet signal."""
        self.monitor.set_codec_info("mSBC", 16000)
        for _ in range(50):
            signal = self._generate_test_audio(frequency=1000, amplitude=0.001)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes)
        
        acceptable, reason = self.monitor.is_quality_acceptable()
        
        self.assertFalse(acceptable)
        self.assertIn("quiet", reason.lower())
    
    # ========== Logging Tests ==========
    
    def test_log_metrics(self):
        """Test metrics logging."""
        # Process some frames
        for i in range(100):
            signal = self._generate_test_audio(frequency=440, amplitude=0.3)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes)
            
            # Log every 50 frames
            self.monitor.log_metrics(interval_frames=50)
        
        # Should have logged twice (at frame 50 and 100)
        # This test mainly checks it doesn't crash
        self.assertEqual(self.monitor.frames_analyzed, 100)
    
    # ========== Reset Tests ==========
    
    def test_reset(self):
        """Test resetting monitor."""
        # Process some frames
        for _ in range(20):
            signal = self._generate_test_audio(frequency=440, amplitude=0.3)
            signal_bytes = self._audio_to_bytes(signal)
            self.monitor.analyze_frame(signal_bytes)
        
        self.assertEqual(self.monitor.frames_analyzed, 20)
        
        # Reset
        self.monitor.reset()
        
        self.assertEqual(self.monitor.frames_analyzed, 0)
    
    # ========== Edge Cases ==========
    
    def test_empty_frame(self):
        """Test handling empty frame."""
        with self.assertRaises((ValueError, Exception)):
            self.monitor.analyze_frame(b'')
    
    def test_wrong_size_frame(self):
        """Test handling wrong size frame."""
        short_audio = np.zeros(100, dtype=np.float32)
        short_bytes = self._audio_to_bytes(short_audio)
        
        # Should handle gracefully
        try:
            self.monitor.analyze_frame(short_bytes)
        except (ValueError, Exception):
            pass  # Expected
    
    def test_metrics_before_any_frames(self):
        """Test getting metrics before processing any frames."""
        metrics = self.monitor.get_current_metrics()
        
        self.assertIsInstance(metrics, AudioQualityMetrics)
        self.assertEqual(metrics.rms_level_db, -float('inf'))
    
    # ========== Integration Tests ==========
    
    def test_continuous_monitoring(self):
        """Test continuous monitoring over extended period."""
        self.monitor.set_codec_info("mSBC", 16000)
        
        # Simulate 10 seconds of audio (500 frames)
        for i in range(500):
            # Vary signal characteristics
            if i < 100:
                # Silence
                audio = np.zeros(self.frame_size, dtype=np.float32)
                has_voice = False
            elif i < 400:
                # Speech
                audio = self._generate_test_audio(
                    frequency=200 + (i % 100) * 5,
                    amplitude=0.2 + (i % 50) * 0.005
                )
                has_voice = True
            else:
                # Noise
                audio = np.random.normal(0, 0.05, self.frame_size).astype(np.float32)
                has_voice = False
            
            audio_bytes = self._audio_to_bytes(audio)
            self.monitor.analyze_frame(audio_bytes, has_voice=has_voice)
        
        # Check final statistics
        stats = self.monitor.get_statistics()
        self.assertEqual(stats['total_frames'], 500)
        
        # Voice activity should be ~60% (300/500)
        self.assertAlmostEqual(stats['voice_activity_percent'], 60.0, delta=5)
    
    def test_real_world_scenario(self):
        """Test realistic audio quality monitoring scenario."""
        monitor = AudioMonitor(sample_rate=16000, window_size=100)
        monitor.set_codec_info("mSBC", 16000)
        
        # Simulate call scenario
        # 1. Initial silence (noise calibration)
        for _ in range(25):
            noise = np.random.normal(0, 0.02, self.frame_size).astype(np.float32)
            monitor.analyze_frame(self._audio_to_bytes(noise), has_voice=False)
        
        # 2. Speech with background noise
        for _ in range(100):
            signal = self._generate_test_audio(frequency=300, amplitude=0.25)
            noise = np.random.normal(0, 0.02, self.frame_size).astype(np.float32)
            speech = signal + noise
            monitor.analyze_frame(self._audio_to_bytes(speech), has_voice=True)
        
        # 3. Pauses
        for _ in range(25):
            noise = np.random.normal(0, 0.02, self.frame_size).astype(np.float32)
            monitor.analyze_frame(self._audio_to_bytes(noise), has_voice=False)
        
        # Check quality
        acceptable, reason = monitor.is_quality_acceptable()
        stats = monitor.get_statistics()
        
        # Should be acceptable quality
        self.assertTrue(acceptable or "Good" in reason or "Fair" in reason)
        self.assertEqual(stats['total_frames'], 150)


if __name__ == '__main__':
    unittest.main()
