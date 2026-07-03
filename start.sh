#!/usr/bin/env bash
# One command to run: auto HTTPS cert + server. Browser: click "Proceed" once → mic works.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8003}"
HOST="${HOST:-0.0.0.0}"
CERT_DIR="./certs"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  PORT="${PORT:-8003}"
fi

if [[ ! -f "${CERT_DIR}/key.pem" || ! -f "${CERT_DIR}/cert.pem" ]]; then
  IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  NAME="$(hostname 2>/dev/null || echo localhost)"
  echo ">>> Creating HTTPS certificate (first run only)..."
  bash scripts/generate_ssl.sh "$CERT_DIR" "$NAME" "${IP:-127.0.0.1}"
fi

if [[ -d venv ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo ""
echo "============================================"
echo "  Local Transcript"
echo "  https://${IP:-localhost}:${PORT}"
echo "  https://localhost:${PORT}"
echo ""
echo "  First time in browser: Advanced → Proceed"
echo "  Then allow microphone."
echo "============================================"
echo ""

exec uvicorn app.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --ssl-keyfile "${CERT_DIR}/key.pem" \
  --ssl-certfile "${CERT_DIR}/cert.pem"
