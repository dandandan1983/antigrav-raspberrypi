#!/usr/bin/env python3
"""
Audio Quality Monitor Module for RPi Hands-Free Headset

This module monitors real-time audio quality metrics:
- Signal-to-Noise Ratio (SNR)
- RMS level tracking
- Clipping detection
- Voice activity percentage
- Codec status
- Latency estimation
"""

import logging
import numpy as np
import time
from typing import Dict, Optional
from collections import deque
from dataclasses import dataclass


@dataclass
class AudioQualityMetrics:
    """Audio quality metrics data class."""
    timestamp: float
    rms_level_db: float
    peak_level_db: float
    snr_db: float
    clipping_percent: float
    voice_activity_percent: float
    codec: str
    sample_rate: int
    latency_ms: float


class AudioMonitor:
    """Real-time audio quality monitoring."""
    
    def __init__(self, sample_rate: int = 16000, window_size: int = 100):
        """
        Initialize audio monitor.
        
        Args:
            sample_rate: Audio sample rate in Hz
            window_size: Number of frames to average for statistics
        """
        self.sample_rate = sample_rate
        self.window_size = window_size
        
        # Metric buffers
        self.rms_buffer = deque(maxlen=window_size)
        self.peak_buffer = deque(maxlen=window_size)
        self.clip_buffer = deque(maxlen=window_size)
        self.voice_buffer = deque(maxlen=window_size)
        
        # Noise estimation
        self.noise_floor = 1e-6
        self.noise_samples = []
        
        # Codec info
        self.current_codec = "CVSD"
        self.current_sample_rate = sample_rate
        
        # Latency tracking
        self.capture_timestamps = deque(maxlen=10)
        self.output_timestamps = deque(maxlen=10)
        
        # Statistics
        self.frames_monitored = 0
        self.total_clipping_frames = 0
        
        logging.info("AudioMonitor initialized")
    
    def analyze_frame(self, audio_data: bytes, has_voice: bool = True) -> None:
        """
        Analyze single audio frame.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            has_voice: Whether frame contains voice
        """
        # Convert to numpy array
        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        
        # Calculate RMS level
        rms = np.sqrt(np.mean(audio_float ** 2))
        self.rms_buffer.append(rms)
        
        # Calculate peak level
        peak = np.max(np.abs(audio_float))
        self.peak_buffer.append(peak)
        
        # Detect clipping
        clipping_samples = np.sum(np.abs(audio_int16) >= 32767)
        clipping_percent = (clipping_samples / len(audio_int16)) * 100
        self.clip_buffer.append(clipping_percent)
        
        if clipping_percent > 0:
            self.total_clipping_frames += 1
        
        # Track voice activity
        self.voice_buffer.append(1.0 if has_voice else 0.0)
        
        # Update noise floor during silence
        if not has_voice and rms > 0:
            self.noise_samples.append(rms)
            if len(self.noise_samples) > 50:
                self.noise_floor = np.median(self.noise_samples[-50:])
        
        self.frames_monitored += 1
    
    def record_capture_timestamp(self) -> None:
        """Record timestamp when audio was captured."""
        self.capture_timestamps.append(time.time())
    
    def record_output_timestamp(self) -> None:
        """Record timestamp when audio was output."""
        self.output_timestamps.append(time.time())
    
    def estimate_latency(self) -> float:
        """
        Estimate end-to-end latency in milliseconds.
        
        Returns:
            Estimated latency in ms
        """
        if len(self.capture_timestamps) < 2 or len(self.output_timestamps) < 2:
            return 0.0
        
        # Calculate average delay between capture and output
        latencies = []
        for cap_time in list(self.capture_timestamps)[-5:]:
            # Find closest output timestamp
            output_times = list(self.output_timestamps)[-5:]
            if output_times:
                closest_output = min(output_times, key=lambda x: abs(x - cap_time))
                if closest_output > cap_time:
                    latency = (closest_output - cap_time) * 1000  # Convert to ms
                    latencies.append(latency)
        
        if latencies:
            return np.mean(latencies)
        return 0.0
    
    def get_current_metrics(self) -> AudioQualityMetrics:
        """
        Get current audio quality metrics.
        
        Returns:
            AudioQualityMetrics object
        """
        # Calculate averages from buffers
        avg_rms = np.mean(list(self.rms_buffer)) if self.rms_buffer else 1e-6
        avg_peak = np.mean(list(self.peak_buffer)) if self.peak_buffer else 1e-6
        avg_clip = np.mean(list(self.clip_buffer)) if self.clip_buffer else 0.0
        avg_voice = np.mean(list(self.voice_buffer)) if self.voice_buffer else 0.0
        
        # Convert to dB
        rms_db = 20 * np.log10(avg_rms) if avg_rms > 0 else -100
        peak_db = 20 * np.log10(avg_peak) if avg_peak > 0 else -100
        
        # Calculate SNR
        if self.noise_floor > 0 and avg_rms > self.noise_floor:
            snr_db = 20 * np.log10(avg_rms / self.noise_floor)
        else:
            snr_db = 0.0
        
        # Estimate latency
        latency = self.estimate_latency()
        
        return AudioQualityMetrics(
            timestamp=time.time(),
            rms_level_db=rms_db,
            peak_level_db=peak_db,
            snr_db=snr_db,
            clipping_percent=avg_clip,
            voice_activity_percent=avg_voice * 100,
            codec=self.current_codec,
            sample_rate=self.current_sample_rate,
            latency_ms=latency
        )
    
    def set_codec_info(self, codec: str, sample_rate: int) -> None:
        """
        Update codec information.
        
        Args:
            codec: Codec name (e.g., "mSBC", "CVSD")
            sample_rate: Sample rate in Hz
        """
        self.current_codec = codec
        self.current_sample_rate = sample_rate
        logging.info(f"Codec updated: {codec} @ {sample_rate}Hz")
    
    def get_statistics(self) -> dict:
        """
        Get overall statistics.
        
        Returns:
            Dictionary of statistics
        """
        metrics = self.get_current_metrics()
        
        clipping_rate = (self.total_clipping_frames / max(1, self.frames_monitored)) * 100
        
        return {
            'frames_monitored': self.frames_monitored,
            'current_rms_db': metrics.rms_level_db,
            'current_peak_db': metrics.peak_level_db,
            'current_snr_db': metrics.snr_db,
            'current_clipping_percent': metrics.clipping_percent,
            'overall_clipping_rate': clipping_rate,
            'voice_activity_percent': metrics.voice_activity_percent,
            'codec': metrics.codec,
            'sample_rate': metrics.sample_rate,
            'estimated_latency_ms': metrics.latency_ms,
            'noise_floor_db': 20 * np.log10(self.noise_floor) if self.noise_floor > 0 else -100
        }
    
    def log_metrics(self, interval_frames: int = 50) -> None:
        """
        Log metrics at regular intervals.
        
        Args:
            interval_frames: Log every N frames
        """
        if self.frames_monitored % interval_frames == 0 and self.frames_monitored > 0:
            stats = self.get_statistics()
            
            logging.info(
                f"Audio Quality - "
                f"RMS: {stats['current_rms_db']:.1f}dB, "
                f"SNR: {stats['current_snr_db']:.1f}dB, "
                f"Clip: {stats['current_clipping_percent']:.2f}%, "
                f"Voice: {stats['voice_activity_percent']:.0f}%, "
                f"Codec: {stats['codec']}, "
                f"Latency: {stats['estimated_latency_ms']:.0f}ms"
            )
    
    def is_quality_acceptable(self) -> tuple[bool, str]:
        """
        Check if audio quality is acceptable.
        
        Returns:
            (acceptable, reason) tuple
        """
        metrics = self.get_current_metrics()
        
        # Check for excessive clipping
        if metrics.clipping_percent > 1.0:
            return False, f"Excessive clipping: {metrics.clipping_percent:.1f}%"
        
        # Check for low SNR
        if metrics.snr_db < 10.0 and self.frames_monitored > 50:
            return False, f"Low SNR: {metrics.snr_db:.1f}dB"
        
        # Check for very low level
        if metrics.rms_level_db < -40.0:
            return False, f"Signal too quiet: {metrics.rms_level_db:.1f}dB"
        
        # Check for excessive latency
        if metrics.latency_ms > 300:
            return False, f"High latency: {metrics.latency_ms:.0f}ms"
        
        return True, "Quality OK"
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.rms_buffer.clear()
        self.peak_buffer.clear()
        self.clip_buffer.clear()
        self.voice_buffer.clear()
        self.capture_timestamps.clear()
        self.output_timestamps.clear()
        self.noise_samples.clear()
        self.frames_monitored = 0
        self.total_clipping_frames = 0
        self.noise_floor = 1e-6
        logging.info("AudioMonitor reset")


if __name__ == "__main__":
    # Test audio monitor
    logging.basicConfig(level=logging.INFO)
    
    monitor = AudioMonitor(sample_rate=16000)
    monitor.set_codec_info("mSBC", 16000)
    
    # Generate test audio
    duration = 1.0
    sample_rate = 16000
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Test signal with noise
    signal_audio = 0.5 * np.sin(2 * np.pi * 1000 * t)
    noise = 0.05 * np.random.randn(len(t))
    test_audio = signal_audio + noise
    
    # Process in frames
    frame_size = 320  # 20ms
    for i in range(0, len(test_audio) - frame_size, frame_size):
        frame = test_audio[i:i+frame_size]
        frame_bytes = (frame * 32768).astype(np.int16).tobytes()
        
        monitor.record_capture_timestamp()
        monitor.analyze_frame(frame_bytes, has_voice=True)
        monitor.log_metrics(interval_frames=25)
    
    print("\nFinal Statistics:")
    stats = monitor.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    acceptable, reason = monitor.is_quality_acceptable()
    print(f"\nQuality: {'✓ Acceptable' if acceptable else '✗ Poor'} - {reason}")
