#!/bin/bash
# Generate self-signed TLS certificates for development/demo
# Usage: bash ssl/generate-dev-certs.sh

set -e

CERT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOMAIN="localhost"
DAYS=365

echo "Generating self-signed TLS certificate for ${DOMAIN}..."

openssl req -x509 -nodes -days ${DAYS} \
  -newkey rsa:2048 \
  -keyout "${CERT_DIR}/privkey.pem" \
  -out "${CERT_DIR}/fullchain.pem" \
  -subj "/C=US/ST=California/L=LosAngeles/O=InfectionIQ/CN=${DOMAIN}" \
  -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},IP:127.0.0.1"

echo "Certificates generated:"
echo "  ${CERT_DIR}/fullchain.pem"
echo "  ${CERT_DIR}/privkey.pem"
echo ""
echo "For production, replace with real certificates from Let's Encrypt:"
echo "  certbot certonly --standalone -d your-domain.com"
