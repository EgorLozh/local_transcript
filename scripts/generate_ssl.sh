#!/usr/bin/env bash
# Self-signed TLS cert for uvicorn (no nginx). Microphone works over HTTPS.
set -euo pipefail

CERT_DIR="${1:-./certs}"
HOSTNAME="${2:-$(hostname)}"
IP="${3:-}"

mkdir -p "$CERT_DIR"

SAN="DNS:localhost,DNS:${HOSTNAME}"
if [[ -n "$IP" ]]; then
  SAN="${SAN},IP:${IP},IP:127.0.0.1"
else
  SAN="${SAN},IP:127.0.0.1"
fi

echo "Generating certificate in ${CERT_DIR}"
echo "SAN: ${SAN}"

openssl req -x509 -newkey rsa:4096 \
  -keyout "${CERT_DIR}/key.pem" \
  -out "${CERT_DIR}/cert.pem" \
  -days 825 -nodes \
  -subj "/CN=${HOSTNAME}" \
  -addext "subjectAltName=${SAN}"

chmod 600 "${CERT_DIR}/key.pem"
echo ""
echo "Done. Start server:"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8003 \\"
echo "    --ssl-keyfile=${CERT_DIR}/key.pem --ssl-certfile=${CERT_DIR}/cert.pem"
echo ""
echo "Open: https://${IP:-localhost}:8003"
echo "Browser will warn about self-signed cert — accept once (Advanced → Proceed)."
