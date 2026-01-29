#!/bin/bash
#
# Installation script for Raspberry Pi Hands-Free Headset
# This script installs all dependencies and configures the system
#

set -e  # Exit on error

echo "=========================================="
echo "RPi Hands-Free Headset Installation"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ] || ! grep -q "Raspberry Pi" /proc/device-tree/model; then
    echo "WARNING: This script is designed for Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Please do not run this script as root"
    echo "Usage: ./install.sh"
    exit 1
fi

echo "Step 1: Updating system packages..."
sudo apt update
sudo apt upgrade -y

echo ""
echo "Step 2: Installing Bluetooth packages..."
sudo apt install -y \
    bluez \
    bluez-tools \
    bluez-firmware \
    python3-bluez

echo ""
echo "Step 3: Installing PipeWire and audio packages..."
sudo apt install -y \
    pipewire \
    pipewire-audio-client-libraries \
    libspa-0.2-bluetooth \
    wireplumber \
    alsa-utils \
    libasound2-dev \
    libspeexdsp-dev \
    swig

# Enable PipeWire services
echo "Enabling PipeWire services..."
systemctl --user enable pipewire pipewire-pulse wireplumber
systemctl --user start pipewire pipewire-pulse wireplumber

# Disable conflicting services
echo "Disabling conflicting services (PulseAudio and oFono)..."
sudo systemctl stop pulseaudio ofono || true
sudo systemctl disable pulseaudio ofono || true

echo ""
echo "Step 4: Installing Python and development tools..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    python3-gi \
    python3-dbus

echo ""
echo "Step 5: Installing GPIO libraries..."
sudo apt install -y \
    python3-rpi.gpio \
    python3-gpiozero

echo ""
echo "Step 6: Creating virtual environment..."
python3 -m venv --system-site-packages venv
source venv/bin/activate

echo ""
echo "Step 7: Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 8: Configuring Bluetooth..."
sudo cp system/bluetooth/main.conf /etc/bluetooth/main.conf
sudo systemctl restart bluetooth
sudo systemctl enable bluetooth

echo ""
echo "Step 9: Configuring audio..."
# Add user to audio group
sudo usermod -a -G audio,bluetooth,gpio $USER

# Configure PipeWire for Bluetooth HFP
if [ ! -d ~/.config/pipewire ]; then
    mkdir -p ~/.config/pipewire
fi

cat > ~/.config/pipewire/pipewire.conf << EOF
context.properties = {
    default.clock.rate          = 48000
    default.clock.allowed-rates = [ 48000 ]
    default.clock.quantum       = 1024
    default.clock.min-quantum   = 32
    default.clock.max-quantum   = 2048
    default.video.width         = 640
    default.video.height        = 480
    default.video.rate.num      = 25
    default.video.rate.denom    = 1
    default.quantum             = 1024
    default.rate                = 48000
    default.channels            = 2
    default.position            = [ FL FR ]
}
EOF

cat > ~/.config/pipewire/media-session.d/bluez-monitor.conf << EOF
bluez-monitor.properties = {
    properties = {
        bluez5.enable-hfp = true
        bluez5.enable-hsp = false
        bluez5.enable-a2dp = true
    }
}
EOF


echo ""
echo "Step 10: Setting up systemd service..."
sudo sed "s|/home/pi|$HOME|g" system/systemd/rpi-handsfree.service > /tmp/rpi-handsfree.service
sudo sed -i "s|User=pi|User=$USER|g" /tmp/rpi-handsfree.service
sudo sed -i "s|Group=pi|Group=$USER|g" /tmp/rpi-handsfree.service
sudo mv /tmp/rpi-handsfree.service /etc/systemd/system/rpi-handsfree.service
sudo systemctl daemon-reload

echo ""
echo "Step 11: Creating log directory..."
sudo mkdir -p /var/log
sudo touch /var/log/rpi-handsfree.log
sudo chown $USER:$USER /var/log/rpi-handsfree.log

echo ""
echo "Step 12: Setting up permissions..."
# Add user to bluetooth group
sudo usermod -a -G bluetooth $USER

# Enable GPIO access
sudo usermod -a -G gpio $USER

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Reboot your Raspberry Pi: sudo reboot"
echo "2. After reboot, enable the service: sudo systemctl enable rpi-handsfree"
echo "3. Start the service: sudo systemctl start rpi-handsfree"
echo "4. Check status: sudo systemctl status rpi-handsfree"
echo "5. View logs: journalctl -u rpi-handsfree -f"
echo ""
echo "To test manually without service:"
echo "  cd $PWD"
echo "  source venv/bin/activate"
echo "  python3 src/main.py"
echo ""
echo "Make your phone discoverable and pair it with 'RPi Hands-Free'"
echo ""
