#!/bin/bash
# Generate self-signed TLS certificates for local development.
# Usage: ./generate-dev-certs.sh
# Output: certs/server.crt, certs/server.key

set -euo pipefail

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
    echo "Certificates already exist in $CERT_DIR — skipping generation."
    echo "Delete them and re-run to regenerate."
    exit 0
fi

echo "Generating self-signed TLS certificate for local development..."

openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "/C=US/ST=Dev/L=Local/O=DrugDesigner/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "$CERT_DIR/server.key"
chmod 644 "$CERT_DIR/server.crt"

echo "Done. Certificates written to:"
echo "  $CERT_DIR/server.crt"
echo "  $CERT_DIR/server.key"
