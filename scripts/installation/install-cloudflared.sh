#!/bin/bash
# install-cloudflared.sh — installe et configure cloudflared sur le RPi5
# Usage : bash install-cloudflared.sh <TOKEN>

set -e

TOKEN="${1}"

if [ -z "$TOKEN" ]; then
  echo "Usage: bash install-cloudflared.sh <TOKEN>"
  echo "Le token se trouve dans Cloudflare Zero Trust > Networks > Tunnels > ton tunnel > Configure"
  exit 1
fi

echo "==> Téléchargement de cloudflared (ARM64)..."
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 \
  -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

echo "==> Version installée : $(cloudflared --version)"

echo "==> Configuration du service systemd..."
cloudflared service install "$TOKEN"

echo "==> Démarrage du service..."
systemctl enable cloudflared
systemctl start cloudflared
systemctl status cloudflared --no-pager

echo ""
echo "✓ cloudflared installé et démarré."
echo "  Vérifie le statut du tunnel dans Cloudflare Zero Trust > Networks > Tunnels"
