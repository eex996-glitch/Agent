#!/bin/bash
# Kali Linux Setup Script for Futures Trading Agent

echo "=================================="
echo "Futures Trading Agent - Kali Setup"
echo "=================================="

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Please don't run as root. Run as normal user."
    exit 1
fi

# Update and install dependencies
echo "[1/5] Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev build-essential libssl-dev libffi-dev

# Create virtual environment
echo "[2/5] Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "[3/5] Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "[4/5] Upgrading pip..."
pip install --upgrade pip

# Install Python packages
echo "[5/5] Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "=================================="
echo "Setup Complete!"
echo "=================================="
echo ""
echo "To use the trading agent:"
echo "  1. Activate venv:  source venv/bin/activate"
echo "  2. Run:            python3 main.py --help"
echo ""
