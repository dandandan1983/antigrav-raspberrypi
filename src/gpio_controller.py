#!/usr/bin/env python3
"""
GPIO Controller Module for RPi Hands-Free Headset

This module manages GPIO hardware interface for buttons and LEDs.
It handles:
- Button input with debouncing
- LED output control  
- Event-driven callbacks
- Status indication
"""

import logging
from typing import Optional, Callable
from enum import Enum
import time

try:
    import RPi.GPIO as GPIO
    from gpiozero import Button, LED
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    GPIO_AVAILABLE = False
    logging.warning("GPIO libraries not available (not running on Raspberry Pi)")


class LEDState(Enum):
    """LED states for visual indication."""
    OFF = "off"
    ON = "on"
    SLOW_BLINK = "slow_blink"      # Connected, idle
    FAST_BLINK = "fast_blink"      # Incoming call
    PULSE = "pulse"                # Active call


class GPIOController:
    """Manages GPIO buttons and LEDs for the hands-free system."""
    
    def __init__(self, 
                 button_answer_pin: int = 17,
                 button_reject_pin: int = 27,
                 button_vol_up_pin: int = 22,
                 button_vol_down_pin: int = 23,
                 led_status_pin: int = 24,
                 led_call_pin: int = 25,
                 debounce_time: float = 0.2):
        """
        Initialize GPIO Controller.
        
        Args:
            button_answer_pin: GPIO pin for answer/hangup button
            button_reject_pin: GPIO pin for reject button
            button_vol_up_pin: GPIO pin for volume up button
            button_vol_down_pin: GPIO pin for volume down button
            led_status_pin: GPIO pin for status LED
            led_call_pin: GPIO pin for call LED
            debounce_time: Button debounce time in seconds
        """
        self.gpio_available = GPIO_AVAILABLE
        
        # GPIO pins
        self.button_answer_pin = button_answer_pin
        self.button_reject_pin = button_reject_pin
        self.button_vol_up_pin = button_vol_up_pin
        self.button_vol_down_pin = button_vol_down_pin
        self.led_status_pin = led_status_pin
        self.led_call_pin = led_call_pin
        self.debounce_time = debounce_time
        
        # GPIO objects (if available)
        self.button_answer: Optional[Button] = None
        self.button_reject: Optional[Button] = None
        self.button_vol_up: Optional[Button] = None
        self.button_vol_down: Optional[Button] = None
        self.led_status: Optional[LED] = None
        self.led_call: Optional[LED] = None
        
        # Callbacks
        self.on_answer_pressed: Optional[Callable] = None
        self.on_reject_pressed: Optional[Callable] = None
        self.on_vol_up_pressed: Optional[Callable] = None
        self.on_vol_down_pressed: Optional[Callable] = None
        
        # LED states
        self.status_led_state = LEDState.OFF
        self.call_led_state = LEDState.OFF
        
        logging.info("GPIOController initialized")
    
    def initialize(self) -> bool:
        """
        Initialize GPIO pins.
        
        Returns:
            True if successful
        """
        if not self.gpio_available:
            logging.warning("GPIO not available, running in mock mode")
            return True  # Return True for testing on non-Pi systems
        
        try:
            # Initialize buttons with pull-up resistors
            self.button_answer = Button(
                self.button_answer_pin,
                pull_up=True,
                bounce_time=self.debounce_time
            )
            self.button_answer.when_pressed = self._handle_answer_pressed
            
            self.button_reject = Button(
                self.button_reject_pin,
                pull_up=True,
                bounce_time=self.debounce_time
            )
            self.button_reject.when_pressed = self._handle_reject_pressed
            
            self.button_vol_up = Button(
                self.button_vol_up_pin,
                pull_up=True,
                bounce_time=self.debounce_time
            )
            self.button_vol_up.when_pressed = self._handle_vol_up_pressed
            
            self.button_vol_down = Button(
                self.button_vol_down_pin,
                pull_up=True,
                bounce_time=self.debounce_time
            )
            self.button_vol_down.when_pressed = self._handle_vol_down_pressed
            
            # Initialize LEDs
            self.led_status = LED(self.led_status_pin)
            self.led_call = LED(self.led_call_pin)
            
            logging.info("GPIO initialized successfully")
            return True
            
        except Exception as e:
            logging.error(f"Failed to initialize GPIO: {e}")
            return False
    
    def _handle_answer_pressed(self) -> None:
        """Handle answer button press."""
        logging.info("Answer button pressed")
        if self.on_answer_pressed:
            self.on_answer_pressed()
    
    def _handle_reject_pressed(self) -> None:
        """Handle reject button press."""
        logging.info("Reject button pressed")
        if self.on_reject_pressed:
            self.on_reject_pressed()
    
    def _handle_vol_up_pressed(self) -> None:
        """Handle volume up button press."""
        logging.info("Volume up button pressed")
        if self.on_vol_up_pressed:
            self.on_vol_up_pressed()
    
    def _handle_vol_down_pressed(self) -> None:
        """Handle volume down button press."""
        logging.info("Volume down button pressed")
        if self.on_vol_down_pressed:
            self.on_vol_down_pressed()
    
    def set_status_led(self, state: LEDState) -> None:
        """
        Set status LED state.
        
        Args:
            state: LED state to set
        """
        if not self.led_status:
            logging.debug(f"Mock: Status LED -> {state.value}")
            return
        
        self.status_led_state = state
        
        if state == LEDState.OFF:
            self.led_status.off()
        elif state == LEDState.ON:
            self.led_status.on()
        elif state == LEDState.SLOW_BLINK:
            self.led_status.blink(on_time=1.0, off_time=1.0)
        elif state == LEDState.FAST_BLINK:
            self.led_status.blink(on_time=0.2, off_time=0.2)
        elif state == LEDState.PULSE:
            self.led_status.pulse(fade_in_time=0.5, fade_out_time=0.5)
        
        logging.info(f"Status LED set to {state.value}")
    
    def set_call_led(self, state: LEDState) -> None:
        """
        Set call LED state.
        
        Args:
            state: LED state to set
        """
        if not self.led_call:
            logging.debug(f"Mock: Call LED -> {state.value}")
            return
        
        self.call_led_state = state
        
        if state == LEDState.OFF:
            self.led_call.off()
        elif state == LEDState.ON:
            self.led_call.on()
        elif state == LEDState.SLOW_BLINK:
            self.led_call.blink(on_time=1.0, off_time=1.0)
        elif state == LEDState.FAST_BLINK:
            self.led_call.blink(on_time=0.2, off_time=0.2)
        elif state == LEDState.PULSE:
            self.led_call.pulse(fade_in_time=0.5, fade_out_time=0.5)
        
        logging.info(f"Call LED set to {state.value}")
    
    def indicate_disconnected(self) -> None:
        """Indicate disconnected state."""
        self.set_status_led(LEDState.SLOW_BLINK)
        self.set_call_led(LEDState.OFF)
    
    def indicate_connected(self) -> None:
        """Indicate connected state."""
        self.set_status_led(LEDState.ON)
        self.set_call_led(LEDState.OFF)
    
    def indicate_incoming_call(self) -> None:
        """Indicate incoming call state."""
        self.set_status_led(LEDState.ON)
        self.set_call_led(LEDState.FAST_BLINK)
    
    def indicate_active_call(self) -> None:
        """Indicate active call state."""
        self.set_status_led(LEDState.ON)
        self.set_call_led(LEDState.PULSE)
    
    def cleanup(self) -> None:
        """Cleanup GPIO resources."""
        if not self.gpio_available:
            return
        
        try:
            # Turn off LEDs
            if self.led_status:
                self.led_status.off()
                self.led_status.close()
            
            if self.led_call:
                self.led_call.off()
                self.led_call.close()
            
            # Close buttons
            if self.button_answer:
                self.button_answer.close()
            if self.button_reject:
                self.button_reject.close()
            if self.button_vol_up:
                self.button_vol_up.close()
            if self.button_vol_down:
                self.button_vol_down.close()
            
            logging.info("GPIO cleaned up")
            
        except Exception as e:
            logging.error(f"Error during GPIO cleanup: {e}")


if __name__ == "__main__":
    # Test GPIO controller
    logging.basicConfig(level=logging.INFO)
    
    gpio = GPIOController()
    gpio.initialize()
    
    # Set up test callbacks
    gpio.on_answer_pressed = lambda: print("ANSWER PRESSED!")
    gpio.on_reject_pressed = lambda: print("REJECT PRESSED!")
    gpio.on_vol_up_pressed = lambda: print("VOLUME UP!")
    gpio.on_vol_down_pressed = lambda: print("VOLUME DOWN!")
    
    # Test LED states
    print("Testing LED states...")
    gpio.indicate_disconnected()
    time.sleep(2)
    gpio.indicate_connected()
    time.sleep(2)
    gpio.indicate_incoming_call()
    time.sleep(2)
    gpio.indicate_active_call()
    time.sleep(2)
    
    gpio.cleanup()
