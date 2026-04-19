#!/bin/bash
# =============================================================================
#  bascule.sh — Bascule quotidienne RPi #1 ↔ RPi #2
#
#  Exécuté par cron à 02:00 sur le RPi ACTUELLEMENT ACTIF.
#  Le RPi actif :
#    1. Sync DB + uploads + WhatsApp auth vers le standby
#    2. Adapte le .env du standby pour prod (ORIGIN HTTPS)
#    3. Démarre les conteneurs + cloudflared sur le standby
#    4. Arrête ses propres conteneurs + cloudflared
#    5. Met à jour le flag actif/standby sur les deux
#
#  Fichier flag : /opt/5hostachy/.active (contient "rpi1" ou "rpi2")
#  Si le flag n'existe pas, le script ne fait rien (sécurité).
#
#  Installation cron (sudo crontab sur CHAQUE RPi) :
#    0 2 * * * /opt/5hostachy/bascule.sh >> /var/log/hostachy-bascule.log 2>&1
# =============================================================================
set -euo pipefail

REPO=/opt/5hostachy
FLAG="$REPO/.active"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# ── Identité de ce RPi ───────────────────────────────────────────────
HOSTNAME=$(hostname)
case "$HOSTNAME" in
  PhT-RB5)   SELF="rpi1"; PEER_IP="192.168.1.223"; PEER="rpi2" ;;
  PhT-RB5i2) SELF="rpi2"; PEER_IP="192.168.1.222"; PEER="rpi1" ;;
  *) echo "$LOG_PREFIX ERREUR: hostname inconnu ($HOSTNAME)"; exit 1 ;;
esac

log() { echo "$LOG_PREFIX $*"; }

SSH_CMD="ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o ConnectTimeout=10"

# ── Vérifications ────────────────────────────────────────────────────
if [ ! -f "$FLAG" ]; then
  log "Pas de fichier .active — bascule désactivée. Créez $FLAG avec 'rpi1' ou 'rpi2'."
  exit 0
fi

ACTIVE=$(cat "$FLAG" | tr -d '[:space:]')
if [ "$ACTIVE" != "$SELF" ]; then
  log "Ce RPi ($SELF) n'est pas actif ($ACTIVE) — rien à faire."
  exit 0
fi

# Vérifier que le peer est joignable
if ! $SSH_CMD ptressard@"$PEER_IP" "echo ok" > /dev/null 2>&1; then
  log "ERREUR: RPi peer ($PEER_IP) injoignable — bascule annulée."
  exit 1
fi

log "===== Bascule $SELF → $PEER ====="

# ── 1. Arrêter les conteneurs locaux (sauf pas immédiatement, d'abord sync) ──
log "[1/6] Arrêt des conteneurs locaux..."
cd "$REPO"
docker compose stop
log "  → Conteneurs arrêtés."

# ── 2. Sync DB ───────────────────────────────────────────────────────
log "[2/6] Sync base de données..."
DB_SRC=$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}')
rsync -az --delete -e "$SSH_CMD" "$DB_SRC/" ptressard@"$PEER_IP":/tmp/sync_app_data/
$SSH_CMD ptressard@"$PEER_IP" "sudo rsync -a /tmp/sync_app_data/ \$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}')/ && rm -rf /tmp/sync_app_data"
log "  → DB synchronisée."

# ── 3. Sync uploads ──────────────────────────────────────────────────
log "[3/6] Sync uploads..."
UPL_SRC=$(docker volume inspect 5hostachy_uploads --format '{{.Mountpoint}}')
rsync -az --delete -e "$SSH_CMD" "$UPL_SRC/" ptressard@"$PEER_IP":/tmp/sync_uploads/
$SSH_CMD ptressard@"$PEER_IP" "sudo rsync -a /tmp/sync_uploads/ \$(docker volume inspect 5hostachy_uploads --format '{{.Mountpoint}}')/ && rm -rf /tmp/sync_uploads"
log "  → Uploads synchronisés."

# ── 4. Sync WhatsApp auth_state ──────────────────────────────────────
log "[4/6] Sync WhatsApp auth_state..."
WA_SRC=$(docker volume inspect 5hostachy_whatsapp_auth --format '{{.Mountpoint}}')
rsync -az --delete -e "$SSH_CMD" "$WA_SRC/" ptressard@"$PEER_IP":/tmp/sync_wa_auth/
$SSH_CMD ptressard@"$PEER_IP" "sudo rsync -a /tmp/sync_wa_auth/ \$(docker volume inspect 5hostachy_whatsapp_auth --format '{{.Mountpoint}}')/ && rm -rf /tmp/sync_wa_auth"
log "  → WhatsApp auth synchronisé."

# ── 5. Configurer .env prod sur le peer et démarrer ──────────────────
log "[5/6] Configuration prod + démarrage peer..."
$SSH_CMD ptressard@"$PEER_IP" "
  cd /opt/5hostachy
  # Adapter .env pour prod (HTTPS via tunnel)
  sed -i 's|^ORIGIN=.*|ORIGIN=https://5hostachy.fr|' .env
  sed -i '/^COOKIE_SECURE=/d' .env
  # Démarrer les conteneurs
  docker compose up -d
  # Démarrer cloudflared
  sudo systemctl start cloudflared
"
log "  → Peer démarré en mode production."

# ── 6. Arrêter cloudflared local + mettre à jour les flags ───────────
log "[6/6] Arrêt cloudflared local + mise à jour flags..."
sudo systemctl stop cloudflared

# Remettre le .env local en mode standby (HTTP local pour tests)
case "$SELF" in
  rpi1) sed -i 's|^ORIGIN=.*|ORIGIN=http://192.168.1.222|' "$REPO/.env" ;;
  rpi2) sed -i 's|^ORIGIN=.*|ORIGIN=http://192.168.1.223|' "$REPO/.env" ;;
esac
grep -q '^COOKIE_SECURE=' "$REPO/.env" || echo 'COOKIE_SECURE=false' >> "$REPO/.env"

# Mettre à jour le flag sur les deux
echo "$PEER" > "$FLAG"
$SSH_CMD ptressard@"$PEER_IP" "echo '$PEER' > /opt/5hostachy/.active"

log "===== Bascule terminée : $PEER est maintenant actif ====="
