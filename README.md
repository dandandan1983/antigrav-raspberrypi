# 🎧 Raspberry Pi Hands-Free Bluetooth Headset

A full-featured Bluetooth hands-free headset implementation using Raspberry Pi 4, supporting HSP/HFP profiles for phone calls with complete call control, audio I/O, and GPIO button interface.

## 📋 Features

- ✅ **Bluetooth Connectivity** - HSP/HFP profile support via BlueZ
- ✅ **Call Management** - Answer, reject, and hang up calls via HFP AT commands
- ✅ **Audio I/O** - Microphone capture and speaker output using PulseAudio (or PipeWire)
- ✅ **Volume Control** - Bidirectional volume synchronization with phone
- ✅ **GPIO Controls** - Physical buttons for call and volume control
- ✅ **LED Indicators** - Visual feedback for connection and call status
- ✅ **Auto-Reconnect** - Automatic reconnection to known devices
- ✅ **Systemd Service** - Auto-start on boot

## 🔧 Hardware Requirements

| Component | Specification | Notes |
|-----------|--------------|-------|
| **Raspberry Pi** | Model 4B, 2GB+ RAM | Built-in Bluetooth 5.0 |
| **USB Audio Adapter** | 3.5mm jack | Or I2S HAT for better quality |
| **Microphone** | 3.5mm or USB | Any standard microphone |
| **Speakers** | 3.5mm or USB | Or headphones |
| **Power Supply** | 5V 3A USB-C | Official PSU recommended |
| **Buttons** (optional) | 4x momentary switches | GPIO control |
| **LEDs** (optional) | 2x LEDs + resistors | Status indication |

## 🔌 Audio Connections

### USB Audio Adapter (Recommended)

**Option 1: USB Sound Card with 3.5mm jacks**
```
[USB Audio Adapter] ──USB──> [Raspberry Pi USB Port]
        │
        ├─ 🎤 Microphone Input (Pink/Red 3.5mm jack)
        │     └─ Connect: Electret microphone or headset mic
        │
        └─ 🔊 Audio Output (Green 3.5mm jack)  
              └─ Connect: Headphones, speakers, or earbuds
```

**Recommended USB Audio Adapters:**
- **Generic USB Sound Card** (~$5-10) - Basic stereo in/out
- **Creative Sound Blaster Play! 4** (~$25) - Better quality
- **Sabrent USB Audio Adapter** (~$8) - Compact option
- **UGREEN USB Audio Adapter** (~$12) - Reliable choice

### Built-in Audio (Alternative)

**Raspberry Pi 4 has limited built-in audio:**
```
[RPi 4 Board]
    │
    ├─ 🔊 3.5mm Audio Jack (Analog out only)
    │     └─ Connect: Headphones or amplified speakers
    │          Note: Output quality limited, no microphone input
    │
    └─ 🎤 USB Microphone (Required for input)
          └─ Connect: USB microphone directly to RPi USB port
```

### I2S HAT (Advanced Option)

**For Audiophile Quality:**
```
[I2S Audio HAT] ──40-pin GPIO──> [Raspberry Pi]
        │
        ├─ 🎤 Microphone Array or Analog Input
        └─ 🔊 High-Quality Audio Output
```

**Recommended I2S HATs:**
- **HiFiBerry DAC+ ADC** (~$55) - Professional quality
- **IQaudio DigiAMP+** (~$40) - Built-in amplifier
- **Adafruit MAX98357 I2S** (~$10) - Simple mono output
- **ReSpeaker 2-Mics Pi HAT** (~$15) - Optimized for voice

### Connection Details

#### USB Audio Adapter Setup
1. **Physical Connection:**
   ```
   USB Audio Adapter → Any free USB port on RPi
   Microphone (3.5mm) → Pink/Red jack on adapter
   Speakers/Headphones → Green jack on adapter
   ```

2. **Microphone Types:**
   - **Electret Microphone**: Most common, powered by adapter
   - **Dynamic Microphone**: Professional, no power needed
   - **USB Microphone**: Direct connection (Yeti, Snowball, etc.)
   - **Headset with Mic**: Combined headphones + microphone

3. **Speaker/Output Options:**
   - **Wired Headphones**: Direct 3.5mm connection
   - **Computer Speakers**: Amplified speakers with 3.5mm input
   - **Bluetooth Speakers**: Not recommended (conflicts with phone BT)
   - **Earbuds**: For discrete use

#### Built-in Audio Setup
1. **Audio Output:**
   ```
   RPi 3.5mm jack → Headphones or Amplified Speakers
   ```
   
2. **Microphone Input:**
   ```
   USB Microphone → RPi USB Port (required, no analog mic input)
   ```

#### Power Requirements
- **USB Audio Adapters**: Usually bus-powered (no external power)
- **USB Microphones**: Check power consumption (some need powered hub)
- **I2S HATs**: Powered from RPi GPIO (check current requirements)

### Audio Quality Considerations

| Connection Type | Quality | Latency | Cost | Setup Difficulty |
|-----------------|---------|---------|------|------------------|
| **USB Audio Adapter** | Good | Low | $ | Easy |
| **Built-in 3.5mm + USB Mic** | Basic | Medium | $ | Easy |
| **I2S HAT** | Excellent | Very Low | $$$ | Advanced |
| **USB Professional Mic** | Very Good | Low | $$ | Easy |

### Troubleshooting Audio Connections

**Common Issues:**
- **No microphone input**: Check if using RPi built-in audio (no mic support)
- **Poor audio quality**: Try different USB ports, avoid USB hubs
- **Audio dropouts**: Check power supply adequacy (5V 3A minimum)
- **Echo/feedback**: Use directional microphone, adjust volume levels

**Testing Commands:**
```bash
# List ALSA devices (useful for USB mics/cards)
aplay -l      # Playback devices
arecord -l    # Recording devices

# Test microphone (ALSA utility still works for USB mics)
arecord -f cd -d 5 test.wav
aplay test.wav

# PulseAudio: list sinks/sources and control profiles
pactl list sinks short
pactl list sources short

# Set card profile to headset/HFP (replace <card> with your card name)
pactl set-card-profile <card> headset_head_unit

# Play a file via PulseAudio default sink
paplay test.wav
```

### GPIO Wiring (Optional)

#### Raspberry Pi 4 Pinout Reference
```
      3V3  (1) (2)  5V
    GPIO2  (3) (4)  5V
    GPIO3  (5) (6)  GND
    GPIO4  (7) (8)  GPIO14
      GND  (9) (10) GPIO15
   GPIO17 (11) (12) GPIO18
   GPIO27 (13) (14) GND
   GPIO22 (15) (16) GPIO23
      3V3 (17) (18) GPIO24
   GPIO10 (19) (20) GND
    GPIO9 (21) (22) GPIO25
   GPIO11 (23) (24) GPIO8
      GND (25) (26) GPIO7
```

#### Button Connections
| Component | GPIO Pin | Physical Pin | Connection |
|-----------|----------|--------------|------------|
| **Answer/Hangup Button** | GPIO 17 | Pin 11 | One terminal to GPIO 17, other to GND (Pin 9, 14, 20, or 25) |
| **Reject Call Button** | GPIO 27 | Pin 13 | One terminal to GPIO 27, other to GND |
| **Volume Up Button** | GPIO 22 | Pin 15 | One terminal to GPIO 22, other to GND |
| **Volume Down Button** | GPIO 23 | Pin 16 | One terminal to GPIO 23, other to GND |

#### LED Connections
| Component | GPIO Pin | Physical Pin | Connection |
|-----------|----------|--------------|------------|
| **Status LED** | GPIO 24 | Pin 18 | Anode (long leg) → 220Ω resistor → GPIO 24<br>Cathode (short leg) → GND |
| **Call LED** | GPIO 25 | Pin 22 | Anode (long leg) → 220Ω resistor → GPIO 25<br>Cathode (short leg) → GND |

#### Detailed Wiring Diagram

**Button Wiring:**
```
[Button] ── Terminal 1 ── GPIO Pin (11, 13, 15, or 16)
         └─ Terminal 2 ── GND (Pin 9, 14, 20, or 25)
```

**LED Wiring:**
```
3V3 ── LED Anode (long leg) ── 220Ω Resistor ── GPIO Pin (18 or 22)
                   LED Cathode (short leg) ── GND
```

#### Component Specifications
- **Buttons**: Momentary push buttons (normally open)
- **LEDs**: Standard 5mm LEDs (red recommended)
- **Resistors**: 220Ω for LEDs (prevents overcurrent)
- **Wires**: Jumper wires or breadboard connections

#### Alternative Connection Options
- Use a breadboard for easier prototyping
- GPIO expansion board for cleaner connections
- Pull-up resistors are handled in software (internal pull-ups enabled)

## 📦 Software Requirements

- **Raspberry Pi OS** - Bullseye or Bookworm (latest stable)
- **Python** - 3.9 or higher
- **BlueZ** - 5.55 or higher (Bluetooth stack)
- **PulseAudio** (or PipeWire) - Audio server for routing and managing sinks/sources

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/rpi-handsfree.git
cd rpi-handsfree
```

### 2. Run Installation Script

```bash
chmod +x install.sh
./install.sh
```

The installation script will:
- Update system packages
- Install Bluetooth, audio, and Python dependencies
- Configure BlueZ and PulseAudio
- Set up systemd service
- Configure permissions

### 3. Reboot

```bash
sudo reboot
```

### 4. Enable and Start Service

```bash
sudo systemctl enable rpi-handsfree
sudo systemctl start rpi-handsfree
```

### 5. Pair Your Phone

1. Open Bluetooth settings on your phone
2. Search for devices
3. Select "RPi Hands-Free"
4. Pair using PIN: `0000`

## 🎮 Usage

### Manual Testing

To run manually without systemd service:

```bash
cd rpi-handsfree
source venv/bin/activate
python3 src/main.py
```

### Making Calls

1. **Incoming Call** - LED will blink rapidly
   - Press Answer button or use phone to answer
   - Audio routes through Pi automatically
   
2. **Active Call** - LED pulses slowly
   - Press Answer button again to hang up
   - Use volume buttons to adjust audio

3. **Rejecting Call**
   - Press Reject button during incoming call

### Volume Control

- **Phone → Pi**: Volume changes on phone sync to Pi
- **Pi → Phone**: Button presses sync to phone
- **Range**: 0-15 (HFP standard) mapped to 0-100 (system)

## 📊 System Status

### Check Service Status

```bash
sudo systemctl status rpi-handsfree
```

### View Logs

```bash
# Real-time logs
journalctl -u rpi-handsfree -f

# Last 100 lines
journalctl -u rpi-handsfree -n 100

# Application log file
tail -f /var/log/rpi-handsfree.log
```

### Bluetooth Troubleshooting

```bash
# Check Bluetooth adapter
hciconfig -a

# List paired devices
bluetoothctl paired-devices

# Check Bluetooth service
sudo systemctl status bluetooth
```

### Audio Troubleshooting

```bash
# List audio devices
aplay -l      # Playback devices
arecord -l    # Capture devices

# Test microphone
arecord -f cd test.wav
aplay test.wav

# List PulseAudio sinks
pactl list sinks short

# Check Bluetooth audio profile
pactl list cards
```

## 📁 Project Structure

```
rpi-handsfree/
├── src/
│   ├── main.py              # Main application
│   ├── config.py            # Configuration management
│   ├── bluetooth_manager.py # Bluetooth/BlueZ interface
│   ├── audio_manager.py     # Audio I/O (PulseAudio)
│   ├── call_manager.py      # HFP call control
│   └── gpio_controller.py   # GPIO buttons/LEDs
├── system/
│   ├── bluetooth/
│   │   └── main.conf        # BlueZ configuration
│   ├── systemd/
│   │   └── rpi-handsfree.service
│   └── pulse/
│       └── default.pa       # PulseAudio/pipewire configuration snippets
├── tests/
│   ├── test_bluetooth.py
│   ├── test_audio.py
│   └── test_call.py
├── config.ini               # Application configuration
├── requirements.txt         # Python dependencies
├── install.sh              # Installation script
└── README.md               # This file
```

## ⚙️ Configuration

Edit `config.ini` to customize settings:

```ini
[bluetooth]
device_name = My Headset    # Name visible to phones
discoverable = true         # Auto-discoverable mode
auto_reconnect = true       # Reconnect to last device

[audio]
sample_rate = 16000        # 8000 or 16000 Hz
channels = 1               # Mono audio
buffer_size = 2048         # Audio buffer size

[gpio]
# Customize GPIO pins
button_answer = 17
led_status = 24

[misc]
log_level = INFO           # DEBUG for troubleshooting
```

## 🔬 Development

### Running Tests

```bash
source venv/bin/activate
python -m pytest tests/
```

### Code Structure

- **Modular Design** - Each component is independent
- **Event-Driven** - Callback-based communication
- **Thread-Safe** - Proper synchronization for audio/Bluetooth
- **Error Handling** - Comprehensive exception handling
- **Logging** - Detailed logs for debugging

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly on real hardware
5. Submit a pull request

## 🐛 Known Issues & Limitations

| Issue | Description | Workaround |
|-------|-------------|------------|
| **Audio Latency** | Bluetooth SCO has inherent ~100-150ms delay | Use buffer optimization |
| **Echo** | Speaker sound picked up by microphone | Use directional mic, lower volume |
| **Quality** | SCO limited to 8/16kHz mono | Use Wide-Band Speech if supported |
| **Compatibility** | Some phones don't fully support HFP | Fallback to HSP implemented |

## 📚 References

- [BlueZ Documentation](http://www.bluez.org/)
- [HFP 1.8 Specification](https://www.bluetooth.org/docman/handlers/downloaddoc.ashx?doc_id=238193)
- [Raspberry Pi GPIO](https://www.raspberrypi.org/documentation/hardware/raspberrypi/)
- [ALSA Project](https://www.alsa-project.org/)
- [PulseAudio Documentation](https://www.freedesktop.org/wiki/Software/PulseAudio/)
- [PipeWire](https://pipewire.org/) (optional replacement for PulseAudio)

## 📝 License

MIT License - See LICENSE file for details

## 👤 Author

Created by [Your Name] - Based on [Technical Specification](ТЗ_Raspberry_Pi_Hands_Free.md)

## 🙏 Acknowledgments

- Raspberry Pi Foundation
- BlueZ Project
- ALSA Project
- PulseAudio Team

---

**Version:** 1.0  
**Date:** 2025-11-19  
**Platform:** Raspberry Pi 4 Model B  
**Python:** 3.9+


```bash
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```