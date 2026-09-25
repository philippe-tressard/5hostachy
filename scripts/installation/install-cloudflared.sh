#!/bin/bash
# install-cloudflared.sh — installe et configure cloudflared sur le RPi5
# Usage : bash install-cloudflared.sh <TOKEN>

set -e

TOKEN="${1}"

if [ -z "$TOKEN" ]; then
  echo "Usage: bash install-cloudflared.sh <TOKEN>"
  echo "Le token se trouve dans Cloudflare Zero Trust > Networks > Tunnels > ton tunnel > Ajouter un connecteur :"
  echo "c'est la longue chaîne eyJ… de la commande d'installation — PAS l'« ID du tunnel » (91d1afa9-…)."
  exit 1
fi

# L'identifiant du tunnel a déjà été collé à la place du jeton (25/09/2026, #1318).
# La règle vit dans lib-jeton-tunnel.sh, partagée avec changer-jeton-tunnel.sh.
# shellcheck source=../lib/lib-jeton-tunnel.sh
source "$(dirname "$0")/../lib/lib-jeton-tunnel.sh"
VERDICT=$(verdict_jeton "$TOKEN" "")
if [ "$VERDICT" != "ok" ]; then
  echo "REFUSÉ — $(motif_refus "$VERDICT")"
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
