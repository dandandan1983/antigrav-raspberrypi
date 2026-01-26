#!/usr/bin/env python3
"""
Call Manager Module for RPi Hands-Free Headset

This module manages phone call control using HFP AT commands.
It handles:
- AT command processing
- Call state management
- Answer/reject/hangup operations
- Volume control commands
- Caller ID information
"""

import logging
import socket
from typing import Optional, Callable
from enum import Enum
import threading
import re


class CallState(Enum):
    """Call states."""
    IDLE = "idle"
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    ACTIVE = "active"
    HELD = "held"


class CallManager:
    """Manages phone call control via HFP AT commands."""
    
    # HFP AT Commands
    AT_BRSF = "AT+BRSF"      # Bluetooth Retrieve Supported Features
    AT_CIND = "AT+CIND"      # Call Indicator
    AT_CIND_Q = "AT+CIND?"   # Query current indicator values
    AT_CIND_T = "AT+CIND=?"  # Query indicator mapping
    AT_CMER = "AT+CMER"      # Enable event reporting
    AT_ATA = "ATA"           # Answer call
    AT_CHUP = "AT+CHUP"      # Hang up call
    AT_VGS = "AT+VGS"        # Speaker volume gain
    AT_VGM = "AT+VGM"        # Microphone volume gain
    AT_CLIP = "AT+CLIP"      # Calling Line Identification Presentation
    AT_BCS = "AT+BCS"        # Codec selection
    AT_BCC = "AT+BCC"        # Bluetooth Codec Connection
    
    # CIEV indicator indices (standard HFP mapping)
    CIEV_SERVICE = 1     # Service availability
    CIEV_CALL = 2        # Call active
    CIEV_CALLSETUP = 3   # Call setup status
    CIEV_CALLHELD = 4    # Call held status
    CIEV_SIGNAL = 5      # Signal strength
    CIEV_ROAM = 6        # Roaming status
    CIEV_BATTCHG = 7     # Battery charge
    
    # CIEV callsetup values
    CALLSETUP_NONE = 0       # No call setup
    CALLSETUP_INCOMING = 1   # Incoming call
    CALLSETUP_OUTGOING = 2   # Outgoing call dialing
    CALLSETUP_ALERTING = 3   # Outgoing call alerting
    
    # Supported features (bitmap)
    HF_FEATURES = {
        'EC_NR': 0x01,           # Echo Cancellation/Noise Reduction
        'THREE_WAY': 0x02,       # Three-way calling
        'CLI': 0x04,             # CLI presentation capability
        'VOICE_RECOGNITION': 0x08,  # Voice recognition activation
        'VOLUME': 0x10,          # Remote volume control
        'WIDEBAND': 0x20,        # Wide band speech
    }
    
    def __init__(self):
        """Initialize Call Manager."""
        self.state = CallState.IDLE
        self.caller_id = ""
        self.caller_name = ""
        
        # Volume levels (0-15 for HFP)
        self.speaker_volume = 10
        self.mic_volume = 10
        
        # HFP indicators (updated via +CIEV)
        self.indicators = {
            'service': 0,      # 0=no service, 1=service available
            'call': 0,         # 0=no call, 1=call active
            'callsetup': 0,    # 0=none, 1=incoming, 2=outgoing, 3=alerting
            'callheld': 0,     # 0=none, 1=held+active, 2=held only
            'signal': 0,       # 0-5 signal strength
            'roam': 0,         # 0=home, 1=roaming
            'battchg': 0,      # 0-5 battery level
        }
        
        # Indicator index mapping (populated from +CIND=? response)
        self.indicator_mapping: dict = {}
        
        # AG (Audio Gateway) supported features from +BRSF response
        self.ag_features = 0
        
        # Callbacks
        self.on_incoming_call: Optional[Callable] = None
        self.on_call_answered: Optional[Callable] = None
        self.on_call_ended: Optional[Callable] = None
        self.on_volume_changed: Optional[Callable] = None
        self.on_call_state_changed: Optional[Callable] = None  # New callback
        self.on_codec_selected: Optional[Callable] = None      # Codec negotiation
        
        # RFCOMM socket for AT commands
        self.rfcomm_socket: Optional[socket.socket] = None
        self.rfcomm_thread: Optional[threading.Thread] = None
        self.running = False
        
        logging.info("CallManager initialized")
    
    def initialize(self) -> bool:
        """
        Initialize call manager.
        
        Returns:
            True if successful
        """
        # In a full implementation, this would set up the RFCOMM channel
        # for AT command communication
        logging.info("CallManager ready")
        return True
    
    def connect_rfcomm_fd(self, fd: int) -> bool:
        """
        Connect to RFCOMM channel using file descriptor from HFP profile.
        
        Args:
            fd: File descriptor for RFCOMM channel
            
        Returns:
            True if connected successfully
        """
        try:
            import os
            
            # Create socket from file descriptor
            self.rfcomm_socket = socket.fromfd(
                fd,
                socket.AF_BLUETOOTH,
                socket.SOCK_STREAM,
                socket.BTPROTO_RFCOMM
            )
            
            # Make a duplicate so we own it
            self.rfcomm_socket = socket.socket(fileno=os.dup(fd))
            
            # Start command processing thread
            self.running = True
            self.rfcomm_thread = threading.Thread(
                target=self._process_commands,
                daemon=True
            )
            self.rfcomm_thread.start()
            
            # Send HFP SLC (Service Level Connection) initialization sequence
            self._init_slc()
            
            logging.info(f"RFCOMM connected via fd={fd}")
            return True
            
        except (OSError, socket.error) as e:
            logging.error(f"Failed to connect RFCOMM via fd: {e}")
            return False
    
    def connect_rfcomm(self, address: str, channel: int) -> bool:
        """
        Connect to phone's RFCOMM channel for AT commands.
        
        Args:
            address: Bluetooth address of phone
            channel: RFCOMM channel number
            
        Returns:
            True if connected successfully
        """
        try:
            self.rfcomm_socket = socket.socket(
                socket.AF_BLUETOOTH,
                socket.SOCK_STREAM,
                socket.BTPROTO_RFCOMM
            )
            
            self.rfcomm_socket.connect((address, channel))
            
            # Start command processing thread
            self.running = True
            self.rfcomm_thread = threading.Thread(
                target=self._process_commands,
                daemon=True
            )
            self.rfcomm_thread.start()
            
            # Send initial AT commands
            self._send_at_command(f"{self.AT_BRSF}=31")  # Send features
            self._send_at_command(f"{self.AT_CMER}=3,0,0,1")  # Enable indicators
            self._send_at_command(f"{self.AT_CLIP}=1")  # Enable caller ID
            
            logging.info(f"RFCOMM connected to {address}:{channel}")
            return True
            
        except (OSError, socket.error) as e:
            logging.error(f"Failed to connect RFCOMM: {e}")
            return False
    
    def disconnect_rfcomm(self) -> None:
        """Disconnect RFCOMM channel."""
        self.running = False
        
        if self.rfcomm_thread:
            self.rfcomm_thread.join(timeout=2.0)
            self.rfcomm_thread = None
        
        if self.rfcomm_socket:
            try:
                self.rfcomm_socket.close()
            except:
                pass
            self.rfcomm_socket = None
        
        logging.info("RFCOMM disconnected")
    
    def _send_at_command(self, command: str) -> bool:
        """
        Send AT command to phone.
        
        Args:
            command: AT command string
            
        Returns:
            True if sent successfully
        """
        if not self.rfcomm_socket:
            logging.warning("RFCOMM not connected")
            return False
        
        try:
            # AT commands end with \r\n
            command_bytes = (command + "\r\n").encode('utf-8')
            self.rfcomm_socket.send(command_bytes)
            logging.debug(f"Sent AT command: {command}")
            return True
            
        except socket.error as e:
            logging.error(f"Failed to send AT command: {e}")
            return False
    
    def _process_commands(self) -> None:
        """Process incoming AT commands (runs in separate thread)."""
        logging.info("AT command processing thread started")
        
        buffer = ""
        
        while self.running:
            try:
                # Read data from socket
                data = self.rfcomm_socket.recv(1024)
                if not data:
                    break
                
                buffer += data.decode('utf-8', errors='ignore')
                
                # Process complete lines
                while '\r\n' in buffer:
                    line, buffer = buffer.split('\r\n', 1)
                    line = line.strip()
                    
                    if line:
                        self._handle_at_command(line)
                
            except socket.error as e:
                logging.error(f"Error reading from RFCOMM: {e}")
                break
            except Exception as e:
                logging.error(f"Unexpected error processing commands: {e}")
        
        logging.info("AT command processing thread stopped")
    
    def _handle_at_command(self, command: str) -> None:
        """
        Handle incoming AT command from phone.
        
        Args:
            command: Received AT command
        """
        logging.debug(f"Received: {command}")
        
        # RING - Incoming call
        if command.startswith("RING"):
            self.state = CallState.INCOMING
            if self.on_incoming_call:
                self.on_incoming_call()
            logging.info("Incoming call detected")
        
        # +CLIP - Caller ID
        elif command.startswith("+CLIP:"):
            match = re.search(r'\+CLIP:\s*"([^"]+)"', command)
            if match:
                self.caller_id = match.group(1)
                logging.info(f"Caller ID: {self.caller_id}")
        
        # +VGS - Speaker volume from phone
        elif command.startswith("+VGS:"):
            match = re.search(r'\+VGS:\s*(\d+)', command)
            if match:
                self.speaker_volume = int(match.group(1))
                if self.on_volume_changed:
                    self.on_volume_changed('speaker', self.speaker_volume)
                logging.info(f"Speaker volume: {self.speaker_volume}")
        
        # +VGM - Microphone volume from phone
        elif command.startswith("+VGM:"):
            match = re.search(r'\+VGM:\s*(\d+)', command)
            if match:
                self.mic_volume = int(match.group(1))
                if self.on_volume_changed:
                    self.on_volume_changed('microphone', self.mic_volume)
                logging.info(f"Microphone volume: {self.mic_volume}")
        
        # OK - Command acknowledged
        elif command == "OK":
            logging.debug("Command acknowledged")
        
        # ERROR - Command failed
        elif command == "ERROR":
            logging.warning("AT command error")
        
        # +CIEV - Indicator Event (call state changes)
        elif command.startswith("+CIEV:"):
            self._handle_ciev(command)
        
        # +BRSF - AG supported features
        elif command.startswith("+BRSF:"):
            match = re.search(r'\+BRSF:\s*(\d+)', command)
            if match:
                self.ag_features = int(match.group(1))
                logging.info(f"AG features: {self.ag_features:#06x}")
        
        # +CIND - Indicator values response
        elif command.startswith("+CIND:"):
            self._parse_cind_response(command)
        
        # +BCS - Codec Selection from AG
        elif command.startswith("+BCS:"):
            match = re.search(r'\+BCS:\s*(\d+)', command)
            if match:
                codec_id = int(match.group(1))
                codec_name = "CVSD" if codec_id == 1 else "mSBC" if codec_id == 2 else f"Unknown({codec_id})"
                logging.info(f"Codec selected: {codec_name}")
                # Confirm codec selection
                self._send_at_command(f"{self.AT_BCS}={codec_id}")
                if self.on_codec_selected:
                    self.on_codec_selected(codec_name)
    
    def _init_slc(self) -> None:
        """Initialize HFP Service Level Connection with proper sequence."""
        import time
        
        # HFP SLC initialization sequence:
        # 1. Exchange supported features
        self._send_at_command(f"{self.AT_BRSF}=63")  # Our features (all enabled)
        time.sleep(0.1)
        
        # 2. Query indicator mapping
        self._send_at_command(self.AT_CIND_T)  # Get indicator definitions
        time.sleep(0.1)
        
        # 3. Query current indicator values
        self._send_at_command(self.AT_CIND_Q)  # Get current values
        time.sleep(0.1)
        
        # 4. Enable indicator event reporting
        self._send_at_command(f"{self.AT_CMER}=3,0,0,1")  # Enable CIEV events
        time.sleep(0.1)
        
        # 5. Enable caller ID
        self._send_at_command(f"{self.AT_CLIP}=1")
    
    def _handle_ciev(self, command: str) -> None:
        """
        Handle +CIEV indicator events from AG.
        
        Format: +CIEV: <index>,<value>
        """
        match = re.search(r'\+CIEV:\s*(\d+),\s*(\d+)', command)
        if not match:
            return
        
        idx = int(match.group(1))
        value = int(match.group(2))
        
        old_state = self.state
        
        # Map index to indicator name and update
        if idx == self.CIEV_CALL:
            self.indicators['call'] = value
            if value == 1 and self.state != CallState.ACTIVE:
                self.state = CallState.ACTIVE
                if self.on_call_answered:
                    self.on_call_answered()
                logging.info("Call became active (from CIEV)")
            elif value == 0 and self.state != CallState.IDLE:
                self.state = CallState.IDLE
                self.caller_id = ""
                if self.on_call_ended:
                    self.on_call_ended()
                logging.info("Call ended (from CIEV)")
        
        elif idx == self.CIEV_CALLSETUP:
            self.indicators['callsetup'] = value
            if value == self.CALLSETUP_INCOMING:
                self.state = CallState.INCOMING
                if self.on_incoming_call:
                    self.on_incoming_call()
                logging.info("Incoming call (from CIEV)")
            elif value == self.CALLSETUP_OUTGOING:
                self.state = CallState.OUTGOING
                logging.info("Outgoing call dialing")
            elif value == self.CALLSETUP_ALERTING:
                logging.info("Outgoing call alerting")
            elif value == self.CALLSETUP_NONE and self.indicators['call'] == 0:
                # Call setup ended without active call = rejected/missed
                if self.state in [CallState.INCOMING, CallState.OUTGOING]:
                    self.state = CallState.IDLE
                    if self.on_call_ended:
                        self.on_call_ended()
                    logging.info("Call setup ended (missed/rejected)")
        
        elif idx == self.CIEV_CALLHELD:
            self.indicators['callheld'] = value
            if value > 0:
                self.state = CallState.HELD
                logging.info(f"Call held status: {value}")
        
        elif idx == self.CIEV_SERVICE:
            self.indicators['service'] = value
            logging.debug(f"Service indicator: {value}")
        
        elif idx == self.CIEV_SIGNAL:
            self.indicators['signal'] = value
            logging.debug(f"Signal strength: {value}")
        
        elif idx == self.CIEV_BATTCHG:
            self.indicators['battchg'] = value
            logging.debug(f"Battery level: {value}")
        
        # Notify state change
        if old_state != self.state and self.on_call_state_changed:
            self.on_call_state_changed(self.state)
    
    def _parse_cind_response(self, command: str) -> None:
        """
        Parse +CIND response (either mapping or values).
        
        Mapping format: +CIND: ("service",(0,1)),("call",(0,1)),...
        Values format: +CIND: 1,0,0,0,5,0,5
        """
        content = command.replace("+CIND:", "").strip()
        
        # Check if it's mapping (contains quotes) or values
        if '"' in content:
            # Parse indicator mapping: ("name",(min,max)),...
            pattern = r'\("([^"]+)",\s*\((\d+),(\d+)\)\)'
            matches = re.findall(pattern, content)
            for i, (name, min_val, max_val) in enumerate(matches, 1):
                self.indicator_mapping[i] = name
                logging.debug(f"Indicator {i}: {name} ({min_val}-{max_val})")
        else:
            # Parse current values
            values = [int(v.strip()) for v in content.split(',') if v.strip().isdigit()]
            indicator_names = ['service', 'call', 'callsetup', 'callheld', 'signal', 'roam', 'battchg']
            for i, val in enumerate(values):
                if i < len(indicator_names):
                    self.indicators[indicator_names[i]] = val
            logging.info(f"Initial indicators: {self.indicators}")
    
    def get_indicators(self) -> dict:
        """Return current HFP indicators."""
        return self.indicators.copy()
    
    def answer_call(self) -> bool:
        """
        Answer incoming call.
        
        Returns:
            True if command sent successfully
        """
        if self.state != CallState.INCOMING:
            logging.warning("No incoming call to answer")
            return False
        
        if self._send_at_command(self.AT_ATA):
            self.state = CallState.ACTIVE
            if self.on_call_answered:
                self.on_call_answered()
            logging.info("Call answered")
            return True
        
        return False
    
    def reject_call(self) -> bool:
        """
        Reject incoming call.
        
        Returns:
            True if command sent successfully
        """
        if self.state != CallState.INCOMING:
            logging.warning("No incoming call to reject")
            return False
        
        if self._send_at_command(self.AT_CHUP):
            self.state = CallState.IDLE
            if self.on_call_ended:
                self.on_call_ended()
            logging.info("Call rejected")
            return True
        
        return False
    
    def hangup_call(self) -> bool:
        """
        Hang up active call.
        
        Returns:
            True if command sent successfully
        """
        if self.state not in [CallState.ACTIVE, CallState.OUTGOING]:
            logging.warning("No active call to hang up")
            return False
        
        if self._send_at_command(self.AT_CHUP):
            self.state = CallState.IDLE
            if self.on_call_ended:
                self.on_call_ended()
            logging.info("Call ended")
            return True
        
        return False
    
    def set_speaker_volume(self, volume: int) -> bool:
        """
        Set speaker volume (0-15).
        
        Args:
            volume: Volume level (0-15)
            
        Returns:
            True if command sent successfully
        """
        volume = max(0, min(15, volume))
        
        if self._send_at_command(f"{self.AT_VGS}={volume}"):
            self.speaker_volume = volume
            logging.info(f"Speaker volume set to {volume}")
            return True
        
        return False
    
    def set_microphone_volume(self, volume: int) -> bool:
        """
        Set microphone volume (0-15).
        
        Args:
            volume: Volume level (0-15)
            
        Returns:
            True if command sent successfully
        """
        volume = max(0, min(15, volume))
        
        if self._send_at_command(f"{self.AT_VGM}={volume}"):
            self.mic_volume = volume
            logging.info(f"Microphone volume set to {volume}")
            return True
        
        return False
    
    def cleanup(self) -> None:
        """Cleanup resources."""
        self.disconnect_rfcomm()
        logging.info("CallManager cleaned up")


if __name__ == "__main__":
    # Test call manager
    logging.basicConfig(level=logging.DEBUG)
    
    cm = CallManager()
    cm.initialize()
    
    # Set up test callbacks
    cm.on_incoming_call = lambda: print("INCOMING CALL!")
    cm.on_call_answered = lambda: print("CALL ANSWERED")
    cm.on_call_ended = lambda: print("CALL ENDED")
    
    print("CallManager ready")
    cm.cleanup()
