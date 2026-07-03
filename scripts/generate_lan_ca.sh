#!/usr/bin/env bash
# Local CA + server cert for LAN. Install ca.pem on each device once → trusted HTTPS everywhere.
set -euo pipefail

CERT_DIR="${1:-./certs}"
HOSTNAME="${2:-$(hostname)}"
IPS="${3:-}"

cd "$(dirname "$0")/.."
mkdir -p "$CERT_DIR"

if [[ -z "$IPS" ]]; then
  IPS="$(hostname -I | awk '{print $1}')"
  echo "Auto-detected IP: ${IPS}"
fi

# Build SAN list: hostname + common LAN names + all given IPs
SAN="DNS:${HOSTNAME},DNS:${HOSTNAME}.local,DNS:transcript.lan,DNS:localhost,IP:127.0.0.1"
IFS=',' read -ra IP_LIST <<< "$IPS"
for ip in "${IP_LIST[@]}"; do
  ip="$(echo "$ip" | xargs)"
  [[ -n "$ip" ]] && SAN="${SAN},IP:${ip}"
done

echo "=== Local LAN CA + server certificate ==="
echo "Output: ${CERT_DIR}"
echo "SAN: ${SAN}"
echo ""

# 1. Create CA (valid 10 years)
if [[ ! -f "${CERT_DIR}/ca.pem" ]]; then
  echo "Creating local CA..."
  openssl genrsa -out "${CERT_DIR}/ca-key.pem" 4096
  openssl req -new -x509 -days 3650 -key "${CERT_DIR}/ca-key.pem" \
    -out "${CERT_DIR}/ca.pem" \
    -subj "/CN=Local Transcript LAN CA/O=Local Network/C=RU"
  chmod 600 "${CERT_DIR}/ca-key.pem"
else
  echo "CA already exists, reusing ${CERT_DIR}/ca.pem"
fi

# 2. Server key + cert signed by CA
echo "Creating server certificate..."
openssl genrsa -out "${CERT_DIR}/key.pem" 4096

EXT_FILE="$(mktemp)"
cat > "$EXT_FILE" <<EOF
subjectAltName=${SAN}
extendedKeyUsage=serverAuth
EOF

openssl req -new -key "${CERT_DIR}/key.pem" \
  -out "${CERT_DIR}/server.csr" \
  -subj "/CN=${HOSTNAME}/O=Local Transcript/C=RU"

openssl x509 -req -in "${CERT_DIR}/server.csr" \
  -CA "${CERT_DIR}/ca.pem" -CAkey "${CERT_DIR}/ca-key.pem" -CAcreateserial \
  -out "${CERT_DIR}/cert.pem" -days 825 \
  -extfile "$EXT_FILE"
rm -f "$EXT_FILE" "${CERT_DIR}/server.csr"

chmod 600 "${CERT_DIR}/key.pem"

echo ""
echo "=== Done ==="
echo ""
echo "Start server:"
echo "  uvicorn app.main:app --host 0.0.0.0 --port 8003 \\"
echo "    --ssl-keyfile=${CERT_DIR}/key.pem --ssl-certfile=${CERT_DIR}/cert.pem"
echo ""
echo "Open (any of these, if IP is in SAN):"
for ip in "${IP_LIST[@]}"; do
  ip="$(echo "$ip" | xargs)"
  [[ -n "$ip" ]] && echo "  https://${ip}:8003"
done
echo "  https://${HOSTNAME}.local:8003  (if mDNS works)"
echo "  https://transcript.lan:8003     (add to /etc/hosts on clients)"
echo ""
echo "=== Trust on ALL devices in LAN (once per device) ==="
echo ""
echo "Copy ${CERT_DIR}/ca.pem to each PC/phone and install as trusted root CA:"
echo ""
echo "  Windows:"
echo "    1. Copy ca.pem → rename to ca.crt"
echo "    2. Double-click → Install Certificate → Local Machine"
echo "    3. Place in: Trusted Root Certification Authorities"
echo ""
echo "  macOS:"
echo "    sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ${CERT_DIR}/ca.pem"
echo ""
echo "  Linux (Ubuntu/Debian):"
echo "    sudo cp ${CERT_DIR}/ca.pem /usr/local/share/ca-certificates/local-transcript-ca.crt"
echo "    sudo update-ca-certificates"
echo ""
echo "  Firefox (if still warns): Settings → Privacy → Certificates → Import ca.pem"
echo ""
echo "After installing CA, browsers will trust https:// without warnings."
