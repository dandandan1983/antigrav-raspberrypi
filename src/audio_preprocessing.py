#!/usr/bin/env python3
"""
Audio Preprocessing Module for RPi Hands-Free Headset

This module provides comprehensive audio preprocessing for high-quality
microphone transmission to phones:
- Noise reduction (spectral subtraction, WebRTC VAD)
- Echo cancellation (SpeexDSP AEC)
- Automatic gain control (AGC)
- High-pass filtering
- De-emphasis for speech clarity
"""

import logging
import numpy as np
from scipy import signal
from scipy.fft import rfft, irfft
from typing import Optional, Tuple
from collections import deque
import threading

try:
    import webrtcvad
    WEBRTC_AVAILABLE = True
except ImportError:
    WEBRTC_AVAILABLE = False
    logging.warning("webrtcvad not available, voice activity detection disabled")

try:
    import speexdsp
    SPEEXDSP_AVAILABLE = True
except ImportError:
    SPEEXDSP_AVAILABLE = False
    logging.warning("speexdsp not available, using fallback NLMS echo cancellation")


class AudioPreprocessor:
    """Comprehensive audio preprocessing pipeline."""
    
    def __init__(self,
                 sample_rate: int = 16000,
                 frame_size_ms: int = 20,
                 enable_noise_reduction: bool = True,
                 noise_reduction_level: int = 2,
                 enable_aec: bool = True,
                 enable_agc: bool = True,
                 agc_target_level_db: float = -6.0,
                 enable_highpass: bool = True,
                 highpass_cutoff: float = 80.0):
        """
        Initialize audio preprocessor.
        
        Args:
            sample_rate: Audio sample rate in Hz
            frame_size_ms: Frame size in milliseconds
            enable_noise_reduction: Enable noise reduction
            noise_reduction_level: Noise reduction strength (0-3)
            enable_aec: Enable echo cancellation
            enable_agc: Enable automatic gain control
            agc_target_level_db: Target RMS level in dB
            enable_highpass: Enable high-pass filter
            highpass_cutoff: High-pass filter cutoff frequency in Hz
        """
        self.sample_rate = sample_rate
        self.frame_size = int(sample_rate * frame_size_ms / 1000)
        
        # Feature flags
        self.enable_noise_reduction = enable_noise_reduction
        self.noise_reduction_level = noise_reduction_level
        self.enable_aec = enable_aec
        self.enable_agc = enable_agc
        self.enable_highpass = enable_highpass
        
        # AGC parameters
        self.agc_target_level = 10 ** (agc_target_level_db / 20)  # Convert dB to linear
        self.agc_gain = 1.0
        self.agc_attack = 0.01
        self.agc_release = 0.001
        
        # Noise reduction parameters
        self.noise_profile: Optional[np.ndarray] = None
        self.noise_estimation_frames = 25  # ~500ms at 20ms frames
        self.noise_frames_collected = 0
        self.fft_size = 512
        self.overlap = 0.5
        self.prev_frame: Optional[np.ndarray] = None
        
        # Echo cancellation parameters
        self.aec_filter_length = 1024
        self.aec_filter = np.zeros(self.aec_filter_length)
        self.aec_step_size = 0.5
        self.speaker_buffer = deque(maxlen=self.aec_filter_length * 8)  # Extended for latency
        self.speaker_buffer_lock = threading.Lock()
        
        # SpeexDSP Echo Canceller
        self.speex_echo = None
        if SPEEXDSP_AVAILABLE and self.enable_aec:
            try:
                # frame_size in samples, filter_length in samples (typically 100-500ms worth)
                # For 16kHz, 200ms = 3200 samples filter length (increased for better room echo)
                filter_samples = int(sample_rate * 0.2)  # 200ms tail length
                self.speex_echo = speexdsp.EchoCanceller(
                    self.frame_size, 
                    filter_samples
                )
                logging.info(f"SpeexDSP AEC initialized: frame={self.frame_size}, filter={filter_samples}")
            except Exception as e:
                logging.error(f"Failed to initialize SpeexDSP AEC: {e}")
                self.speex_echo = None
        
        # Fallback NLMS filter coefficients for when SpeexDSP unavailable
        # Increased to 512 taps (~32ms at 16kHz) for better echo cancellation
        self.nlms_weights = np.zeros(512)
        self.nlms_mu = 0.3  # Reduced step size for stability
        
        # High-pass filter
        if self.enable_highpass:
            nyquist = sample_rate / 2
            normalized_cutoff = highpass_cutoff / nyquist
            self.hp_b, self.hp_a = signal.butter(4, normalized_cutoff, btype='high')
            self.hp_zi = signal.lfilter_zi(self.hp_b, self.hp_a)
        
        # WebRTC VAD for voice activity detection
        self.vad = None
        if WEBRTC_AVAILABLE and enable_noise_reduction:
            try:
                self.vad = webrtcvad.Vad(2)  # Aggressiveness: 0-3
            except Exception as e:
                logging.warning(f"Failed to initialize WebRTC VAD: {e}")
        
        # Statistics
        self.frames_processed = 0
        self.total_gain_applied = 0.0
        
        logging.info(f"AudioPreprocessor initialized: {sample_rate}Hz, {frame_size_ms}ms frames")
    
    def process_frame(self, audio_data: bytes) -> bytes:
        """
        Process single audio frame.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            
        Returns:
            Processed audio bytes
        """
        # Convert bytes to numpy array
        audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0
        
        # Apply preprocessing pipeline
        processed = audio_float.copy()
        
        # 1. High-pass filter (remove rumble)
        if self.enable_highpass:
            processed, self.hp_zi = signal.lfilter(
                self.hp_b, self.hp_a, processed, zi=self.hp_zi
            )
        
        # 2. Echo cancellation
        if self.enable_aec:
            processed = self._apply_aec(processed)
        
        # 3. Noise reduction
        if self.enable_noise_reduction:
            processed = self._apply_noise_reduction(processed)
        
        # 4. Automatic gain control
        if self.enable_agc:
            processed = self._apply_agc(processed)
        
        # Convert back to int16
        processed = np.clip(processed * 32768.0, -32768, 32767)
        processed_int16 = processed.astype(np.int16)
        
        self.frames_processed += 1
        
        return processed_int16.tobytes()
    
    def _apply_noise_reduction(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply spectral subtraction noise reduction.
        
        Args:
            audio: Input audio frame
            
        Returns:
            Noise-reduced audio
        """
        # Build noise profile from first few frames
        if self.noise_frames_collected < self.noise_estimation_frames:
            self._update_noise_profile(audio)
            self.noise_frames_collected += 1
            return audio  # Don't process during calibration
        
        if self.noise_profile is None:
            return audio
        
        # Check voice activity
        has_voice = self._detect_voice_activity(audio)
        
        if not has_voice and self.noise_reduction_level > 0:
            # Update noise profile during silence
            self._update_noise_profile(audio)
        
        # Spectral subtraction
        # Pad audio for FFT
        padded = np.pad(audio, (0, self.fft_size - len(audio)), mode='constant')
        
        # Forward FFT
        spectrum = rfft(padded)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)
        
        # Subtract noise
        over_subtraction = 1.0 + (self.noise_reduction_level * 0.5)
        clean_magnitude = magnitude - (over_subtraction * self.noise_profile[:len(magnitude)])
        
        # Apply spectral floor
        spectral_floor = 0.002 * magnitude
        clean_magnitude = np.maximum(clean_magnitude, spectral_floor)
        
        # Reconstruct signal
        clean_spectrum = clean_magnitude * np.exp(1j * phase)
        clean_audio = irfft(clean_spectrum)
        
        return clean_audio[:len(audio)]
    
    def _update_noise_profile(self, audio: np.ndarray) -> None:
        """Update noise spectral profile."""
        padded = np.pad(audio, (0, self.fft_size - len(audio)), mode='constant')
        spectrum = rfft(padded)
        magnitude = np.abs(spectrum)
        
        if self.noise_profile is None:
            self.noise_profile = magnitude
        else:
            # Exponential moving average
            alpha = 0.1
            self.noise_profile = (alpha * magnitude) + ((1 - alpha) * self.noise_profile)
    
    def _detect_voice_activity(self, audio: np.ndarray) -> bool:
        """
        Detect if frame contains voice.
        
        Args:
            audio: Audio frame
            
        Returns:
            True if voice detected
        """
        if self.vad is None:
            # Fallback: simple energy-based VAD
            rms = np.sqrt(np.mean(audio ** 2))
            return rms > 0.01
        
        try:
            # Convert to bytes for WebRTC VAD
            audio_int16 = (audio * 32768).astype(np.int16)
            audio_bytes = audio_int16.tobytes()
            
            # WebRTC VAD requires specific frame sizes
            # Pad or trim to match
            target_size = int(self.sample_rate * 0.01)  # 10ms
            if len(audio_int16) > target_size:
                audio_bytes = audio_int16[:target_size].tobytes()
            
            return self.vad.is_speech(audio_bytes, self.sample_rate)
        except Exception:
            # Fallback on error
            rms = np.sqrt(np.mean(audio ** 2))
            return rms > 0.01
    
    def _apply_aec(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply adaptive echo cancellation using SpeexDSP or NLMS fallback.
        
        Args:
            audio: Input audio with echo (microphone signal)
            
        Returns:
            Echo-cancelled audio
        """
        # Get speaker reference signal from buffer
        with self.speaker_buffer_lock:
            if len(self.speaker_buffer) < len(audio):
                # Not enough reference data yet, return input unchanged
                return audio
            
            # Get aligned reference signal
            speaker_ref = np.array(list(self.speaker_buffer)[:len(audio)])
        
        # Use SpeexDSP if available
        if self.speex_echo is not None:
            try:
                # Convert to int16 for SpeexDSP
                mic_int16 = (audio * 32768).astype(np.int16)
                speaker_int16 = (speaker_ref * 32768).astype(np.int16)
                
                # Process echo cancellation
                output_int16 = self.speex_echo.process(
                    mic_int16.tobytes(),
                    speaker_int16.tobytes()
                )
                
                # Convert back to float
                output = np.frombuffer(output_int16, dtype=np.int16).astype(np.float32) / 32768.0
                return output
                
            except Exception as e:
                logging.error(f"SpeexDSP AEC error: {e}")
                # Fall through to NLMS fallback
        
        # Fallback: NLMS adaptive filter
        return self._apply_nlms_aec(audio, speaker_ref)
    
    def _apply_nlms_aec(self, mic_signal: np.ndarray, speaker_signal: np.ndarray) -> np.ndarray:
        """
        Apply NLMS (Normalized Least Mean Squares) echo cancellation.
        
        Args:
            mic_signal: Microphone input with echo
            speaker_signal: Speaker reference signal
            
        Returns:
            Echo-cancelled signal
        """
        output = np.zeros_like(mic_signal)
        filter_len = len(self.nlms_weights)
        
        # Pad speaker signal for filter
        padded_speaker = np.pad(speaker_signal, (filter_len - 1, 0), mode='constant')
        
        for i in range(len(mic_signal)):
            # Get reference window
            x = padded_speaker[i:i + filter_len][::-1]
            
            # Estimate echo
            echo_estimate = np.dot(self.nlms_weights, x)
            
            # Calculate error (desired = mic - echo)
            error = mic_signal[i] - echo_estimate
            output[i] = error
            
            # Update weights (NLMS)
            norm = np.dot(x, x) + 1e-6  # Regularization
            self.nlms_weights += (self.nlms_mu / norm) * error * x
        
        return output
    
    def _apply_agc(self, audio: np.ndarray) -> np.ndarray:
        """
        Apply automatic gain control.
        
        Args:
            audio: Input audio
            
        Returns:
            Gain-controlled audio
        """
        # Calculate RMS level
        rms = np.sqrt(np.mean(audio ** 2))
        
        if rms < 1e-6:
            return audio  # Avoid division by zero
        
        # Calculate required gain
        target_gain = self.agc_target_level / rms
        
        # Apply attack/release
        if target_gain > self.agc_gain:
            # Attack (increasing gain)
            self.agc_gain += self.agc_attack * (target_gain - self.agc_gain)
        else:
            # Release (decreasing gain)
            self.agc_gain += self.agc_release * (target_gain - self.agc_gain)
        
        # Limit gain to reasonable range
        self.agc_gain = np.clip(self.agc_gain, 0.5, 10.0)
        
        # Apply gain with soft clipping
        gained = audio * self.agc_gain
        
        # Soft clipping to prevent distortion
        gained = np.tanh(gained * 2.0) / 2.0
        
        self.total_gain_applied += self.agc_gain
        
        return gained
    
    def update_speaker_signal(self, speaker_data: bytes) -> None:
        """
        Update speaker signal for echo cancellation.
        Must be called with playback data before it's sent to speakers.
        
        Args:
            speaker_data: Speaker output data (16-bit PCM bytes)
        """
        if not self.enable_aec:
            return
        
        # Convert to float
        speaker_int16 = np.frombuffer(speaker_data, dtype=np.int16)
        speaker_float = speaker_int16.astype(np.float32) / 32768.0
        
        # Add to buffer with thread safety
        with self.speaker_buffer_lock:
            self.speaker_buffer.extend(speaker_float)
    
    def get_quality_metrics(self) -> dict:
        """
        Get audio quality metrics.
        
        Returns:
            Dictionary of quality metrics
        """
        avg_gain = self.total_gain_applied / max(1, self.frames_processed)
        
        metrics = {
            'frames_processed': self.frames_processed,
            'avg_agc_gain': avg_gain,
            'avg_agc_gain_db': 20 * np.log10(avg_gain) if avg_gain > 0 else -100,
            'noise_profile_ready': self.noise_profile is not None,
            'aec_enabled': self.enable_aec,
            'noise_reduction_level': self.noise_reduction_level,
        }
        
        return metrics
    
    def reset_noise_profile(self) -> None:
        """Reset noise profile (e.g., when environment changes)."""
        self.noise_profile = None
        self.noise_frames_collected = 0
        logging.info("Noise profile reset")


if __name__ == "__main__":
    # Test audio preprocessor
    logging.basicConfig(level=logging.INFO)
    
    preprocessor = AudioPreprocessor(
        sample_rate=16000,
        enable_noise_reduction=True,
        enable_agc=True
    )
    
    # Generate test audio (1 second @ 16kHz)
    duration = 1.0
    t = np.linspace(0, duration, int(16000 * duration))
    
    # Test signal: 1kHz tone + noise
    signal_audio = 0.3 * np.sin(2 * np.pi * 1000 * t)
    noise = 0.1 * np.random.randn(len(t))
    test_audio = signal_audio + noise
    
    # Process in frames
    frame_size = 320  # 20ms @ 16kHz
    for i in range(0, len(test_audio) - frame_size, frame_size):
        frame = test_audio[i:i+frame_size]
        frame_bytes = (frame * 32768).astype(np.int16).tobytes()
        
        processed_bytes = preprocessor.process_frame(frame_bytes)
    
    print("Quality metrics:", preprocessor.get_quality_metrics())
