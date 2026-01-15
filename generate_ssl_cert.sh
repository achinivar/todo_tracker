#!/bin/bash

# Generate self-signed SSL certificate for Task Tracker
# This creates a certificate valid for 365 days

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

CERT_FILE="cert.pem"
KEY_FILE="key.pem"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "SSL certificates already exist."
    echo "To regenerate, delete $CERT_FILE and $KEY_FILE first."
    exit 0
fi

echo "Generating self-signed SSL certificate..."
echo "This will create a certificate valid for 365 days."
echo ""

# Get the hostname/IP for the certificate
HOSTNAME=$(hostname)
IP=$(hostname -I | awk '{print $1}')

# Generate certificate
openssl req -x509 -newkey rsa:4096 -nodes \
    -out "$CERT_FILE" \
    -keyout "$KEY_FILE" \
    -days 365 \
    -subj "/C=US/ST=State/L=City/O=Task Tracker/CN=$HOSTNAME" \
    -addext "subjectAltName=DNS:$HOSTNAME,DNS:localhost,IP:127.0.0.1,IP:$IP"

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SSL certificates generated successfully!"
    echo "  Certificate: $CERT_FILE"
    echo "  Private Key: $KEY_FILE"
    echo ""
    echo "Note: Browsers will show a security warning for self-signed certificates."
    echo "This is normal - click 'Advanced' and 'Proceed' to continue."
    echo ""
    chmod 600 "$KEY_FILE"
    chmod 644 "$CERT_FILE"
else
    echo "Error generating SSL certificates."
    exit 1
fi
