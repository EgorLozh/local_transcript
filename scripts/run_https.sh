#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8003}"
HOST="${HOST:-0.0.0.0}"
CERT_DIR="./certs"

if [[ ! -f "${CERT_DIR}/key.pem" || ! -f "${CERT_DIR}/cert.pem" ]]; then
  echo "Certificates not found. Run first:"
  echo "  bash scripts/generate_ssl.sh ./certs \$(hostname) YOUR_SERVER_IP"
  exit 1
fi

source venv/bin/activate 2>/dev/null || true

exec uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --ssl-keyfile "${CERT_DIR}/key.pem" \
  --ssl-certfile "${CERT_DIR}/cert.pem"
