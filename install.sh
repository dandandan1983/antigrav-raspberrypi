#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
# On Debian/Ubuntu (Raspbian) install system packages required for Bluetooth
# and for building some Python bindings — this avoids building PyBluez from pip
if command -v apt-get >/dev/null 2>&1; then
    echo "Installing system packages for Bluetooth and build dependencies"
    sudo apt-get update
    sudo apt-get install -y python3-bluez libbluetooth-dev bluetooth bluez \
        build-essential pkg-config libglib2.0-dev python3-dev libatlas-base-dev \
        libblas-dev gfortran || true
fi

if [ -f "$ROOT_DIR/requirements.txt" ]; then
    # ensure packaging tools are up-to-date to provide build backends
    pip install --upgrade pip setuptools wheel
    pip install -r "$ROOT_DIR/requirements.txt"
fi

# Ensure log file directory exists and is writable by the `pi` user if present
LOG_FILE="$(python - <<PY
from configparser import ConfigParser
from pathlib import Path
cfg=ConfigParser(); cfg.read('config.ini'); print(cfg.get('misc','log_file',fallback='/var/log/rpi-handsfree.log'))
PY
)"
LOG_DIR="$(dirname "$LOG_FILE")"
if [ ! -d "$LOG_DIR" ]; then
    sudo mkdir -p "$LOG_DIR"
fi
sudo chown $(whoami) "$LOG_DIR" || true
# Ensure state directory exists and is writable
STATE_DIR="$(python - <<PY
from configparser import ConfigParser
from pathlib import Path
cfg=ConfigParser(); cfg.read('config.ini'); print(cfg.get('misc','state_dir',fallback='/var/lib/rpi-handsfree'))
PY
)"
if [ ! -d "$STATE_DIR" ]; then
    sudo mkdir -p "$STATE_DIR"
fi
sudo chown $(whoami) "$STATE_DIR" || true

# Create dedicated service user and ensure ownership
SERVICE_USER="rpi-handsfree"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    echo "Creating system user $SERVICE_USER"
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER" || true
fi

# Ensure project installed to /opt/rpi-handsfree (recommended)
INSTALL_DIR="/opt/rpi-handsfree"
if [ ! -d "$INSTALL_DIR" ]; then
    sudo mkdir -p "$INSTALL_DIR"
fi
sudo cp -r . "$INSTALL_DIR/"
sudo chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"

# Ensure logs and state dir owned by service user
sudo chown -R "$SERVICE_USER":"$SERVICE_USER" "$LOG_DIR" || true
sudo chown -R "$SERVICE_USER":"$SERVICE_USER" "$STATE_DIR" || true

echo "Service user and file ownership configured for $SERVICE_USER"

echo "Install complete. To run manually:"
echo "  source venv/bin/activate"
echo "  python src/main.py"

echo "To install systemd unit (requires sudo):"
if [ -f "$ROOT_DIR/system/rpi-handsfree.service" ]; then
    echo "  sudo cp system/rpi-handsfree.service /etc/systemd/system/"
    echo "  sudo systemctl daemon-reload"
    echo "  sudo systemctl enable rpi-handsfree"
    echo "  sudo systemctl start rpi-handsfree"
else
    echo "  (no system/rpi-handsfree.service file found in project)"
fi
