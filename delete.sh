#!/bin/bash
# Cleanup script for Raspberry Pi Hands-Free Headset

set -e  # Exit on error

# Uninstall ALSA-related packages
echo "Removing ALSA-related packages..."
sudo apt remove --purge -y alsa-utils bluealsa

# Remove ALSA configuration files
echo "Removing ALSA configuration files..."
sudo rm -f /etc/asound.conf ~/.asoundrc

# Disable and remove unused services
echo "Disabling and removing unused services..."
sudo systemctl stop pulseaudio ofono || true
sudo systemctl disable pulseaudio ofono || true

# Remove virtual environment (optional)
read -p "Do you want to remove the virtual environment? (y/N): " remove_venv
if [[ "$remove_venv" == "y" || "$remove_venv" == "Y" ]]; then
    echo "Removing virtual environment..."
    rm -rf venv
fi

# Remove Python dependencies (optional)
read -p "Do you want to remove Python dependencies? (y/N): " remove_deps
if [[ "$remove_deps" == "y" || "$remove_deps" == "Y" ]]; then
    echo "Removing Python dependencies..."
    pip freeze | xargs pip uninstall -y
fi

# Final cleanup
echo "Cleanup complete!"