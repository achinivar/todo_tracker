#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Generate local HTTPS certificates (mkcert) if needed
CERT_DIR=".certs"
CERT_PATH="$CERT_DIR/localhost.pem"
KEY_PATH="$CERT_DIR/localhost-key.pem"

if [ ! -f "$CERT_PATH" ] || [ ! -f "$KEY_PATH" ]; then
    if ! command -v mkcert >/dev/null 2>&1; then
        echo "mkcert is required to generate local HTTPS certificates."
        echo "Install it from https://github.com/FiloSottile/mkcert and run: mkcert -install"
        exit 1
    fi
    echo "Generating local HTTPS certificate with mkcert..."
    mkdir -p "$CERT_DIR"
    mkcert -install
    HOSTNAME="$(hostname)"
    LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [ -n "$LAN_IP" ]; then
        mkcert -key-file "$KEY_PATH" -cert-file "$CERT_PATH" localhost 127.0.0.1 ::1 "$HOSTNAME" "$LAN_IP"
    else
        mkcert -key-file "$KEY_PATH" -cert-file "$CERT_PATH" localhost 127.0.0.1 ::1 "$HOSTNAME"
    fi
fi

# Run the application (HTTPS)
echo "Starting server with HTTPS..."
APP_USE_TLS=true APP_CERT_PATH="$CERT_PATH" APP_KEY_PATH="$KEY_PATH" python app.py

