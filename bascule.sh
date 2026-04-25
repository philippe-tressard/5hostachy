#!/bin/bash
# =============================================================================
#  bascule.sh — Bascule quotidienne RPi #1 ↔ RPi #2  (v2 — sécurisée)
#
#  Exécuté par cron à 02:00 sur le RPi ACTUELLEMENT ACTIF.
#  Séquence :
#    0. Pre-flight : peer joignable, espace disque, DB locale saine
#    1. Sync uploads + WhatsApp auth à chaud (prod toujours UP)
#    2. Stop conteneurs locaux
#    3. WAL checkpoint + integrity check DB locale
#    4. Rsync DB → peer + integrity check DB sur peer
#    5. Start peer + health check API (60s max)
#    6. Start cloudflared peer + vérif URL publique
#    7. Stop cloudflared local + MAJ flags
#
#  Rollback automatique (set +e) si échec en phase 2-6 :
#    → Redémarre conteneurs locaux, maintient cloudflared local actif
#    → Envoie un email d'alerte à ptressard@icloud.com
#
#  Fichier flag : /opt/5hostachy/.active (contient "rpi1" ou "rpi2")
#  Mode test    : bascule.sh --dry-run  (aucune action destructive)
#
#  Installation cron (sudo crontab sur CHAQUE RPi) :
#    0 2 * * * /opt/5hostachy/bascule.sh >> /var/log/hostachy-bascule.log 2>&1
# =============================================================================
set -euo pipefail

REPO=/opt/5hostachy
FLAG="$REPO/.active"
DRY_RUN=false
ALERT_EMAIL="ptressard@icloud.com"
PUBLIC_URL="https://5hostachy.fr/api/health"
HEALTH_TIMEOUT=60   # secondes max pour que l'API peer réponde
CLOUDFLARE_WAIT=90  # secondes max de polling URL publique après start cloudflared peer
CLOUDFLARE_INITIAL_WAIT=10  # attente initiale avant de commencer à poller (tunnel pas établi < 10s)

# ── Mode dry-run ─────────────────────────────────────────────────────
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
drylog() { log "[DRY-RUN] (simulé) $*"; }

run() {
  # Wrapper : en dry-run, affiche la commande sans l'exécuter
  if $DRY_RUN; then
    drylog "$*"
  else
    eval "$*"
  fi
}

# ── Identité de ce RPi ───────────────────────────────────────────────
CUR_HOSTNAME=$(hostname)
case "$CUR_HOSTNAME" in
  PhT-RB5)   SELF="rpi1"; SELF_IP="192.168.1.222"; PEER_IP="192.168.1.223"; PEER="rpi2" ;;
  PhT-RB5i2) SELF="rpi2"; SELF_IP="192.168.1.223"; PEER_IP="192.168.1.222"; PEER="rpi1" ;;
  *) log "ERREUR: hostname inconnu ($CUR_HOSTNAME)"; exit 1 ;;
esac

SSH_CMD="ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no"

# ── Vérifications flag ───────────────────────────────────────────────
if [ ! -f "$FLAG" ]; then
  log "Pas de fichier .active — bascule désactivée."
  exit 0
fi
ACTIVE=$(tr -d '[:space:]' < "$FLAG")
if [ "$ACTIVE" != "$SELF" ]; then
  log "Ce RPi ($SELF) n'est pas actif ($ACTIVE) — rien à faire."
  exit 0
fi

# ── Fonction rollback ────────────────────────────────────────────────
# Appelée via trap ERR — set +e pour éviter une sortie prématurée
ROLLBACK_DONE=false
rollback() {
  local phase="${1:-inconnu}"
  set +e
  log "⚠️  ÉCHEC en phase $phase — rollback en cours..."

  # Redémarrer les conteneurs locaux si arrêtés
  cd "$REPO"
  if docker compose up -d; then
    log "  → Conteneurs locaux relancés."
  else
    log "  ⚠ ÉCHEC relance conteneurs locaux — vérifier manuellement : cd /opt/5hostachy && docker compose up -d"
  fi

  # Cloudflared local : redémarrer si arrêté (peut avoir été stoppé en phase 6 avant rollback)
  systemctl is-active cloudflared > /dev/null 2>&1 || sudo systemctl start cloudflared 2>/dev/null || true
  log "  → Cloudflared local maintenu/relancé."

  # Stopper les conteneurs peer s'ils avaient été démarrés
  $SSH_CMD ptressard@"$PEER_IP" "cd /opt/5hostachy && docker compose stop 2>/dev/null; sudo systemctl stop cloudflared 2>/dev/null" 2>/dev/null || true
  log "  → Conteneurs peer arrêtés (si démarrés)."

  # Supprimer le lock bascule sur le peer
  $SSH_CMD ptressard@"$PEER_IP" "rm -f /opt/5hostachy/.bascule-lock" 2>/dev/null || true
  log "  → Lock bascule supprimé sur le peer."

  # Envoyer un email d'alerte
  send_alert_email "$phase"

  log "⚠️  BASCULE ANNULÉE (phase $phase) — $SELF reste actif."
  ROLLBACK_DONE=true
  exit 1
}

# ── Envoi email d'alerte ─────────────────────────────────────────────
send_alert_email() {
  local phase="${1:-inconnu}"
  local subject="[5Hostachy] ⚠️ Bascule ÉCHOUÉE — phase $phase — $SELF reste actif"
  local body="La bascule automatique du $(date '+%d/%m/%Y à %H:%M') a échoué en phase : $phase

RPi actif : $SELF ($SELF_IP)
RPi peer  : $PEER ($PEER_IP)

Consultez le log complet :
  ssh ptressard@$SELF_IP 'tail -100 /var/log/hostachy-bascule.log'

Action requise : vérifier l'état du peer et relancer la bascule manuellement si nécessaire."

  # Utilise Python/fastapi-mail config déjà présente dans le conteneur API
  docker exec hostachy_api python3 -c "
import smtplib, os
from email.mime.text import MIMEText
msg = MIMEText('''$body''')
msg['Subject'] = '''$subject'''
msg['From'] = os.environ.get('MAIL_FROM', 'noreply@5hostachy.fr')
msg['To'] = '$ALERT_EMAIL'
try:
    s = smtplib.SMTP(os.environ.get('MAIL_SERVER','ssl0.ovh.net'), int(os.environ.get('MAIL_PORT','587')))
    s.starttls()
    s.login(os.environ.get('MAIL_USERNAME',''), os.environ.get('MAIL_PASSWORD',''))
    s.sendmail(msg['From'], ['$ALERT_EMAIL'], msg.as_string())
    s.quit()
    print('Email envoyé.')
except Exception as e:
    print(f'Email KO: {e}')
" 2>/dev/null || log "  (email non envoyé — conteneur API indisponible)"
}

# ── Phase 0 : Pre-flight ─────────────────────────────────────────────
log "===== Bascule $SELF → $PEER ===== $([ $DRY_RUN = true ] && echo '[DRY-RUN]' || true)"
log "[0/7] Pre-flight..."

# Peer joignable ?
if ! $SSH_CMD ptressard@"$PEER_IP" "echo ok" > /dev/null 2>&1; then
  log "ERREUR: Peer ($PEER_IP) injoignable — bascule annulée."
  exit 1
fi
log "  → Peer joignable."

# Espace disque peer suffisant (>= 100 MB libres)
PEER_FREE=$($SSH_CMD ptressard@"$PEER_IP" "df /var/lib/docker --output=avail -B 1M | tail -1 | tr -d ' '" 2>/dev/null || echo 0)
if [ "$PEER_FREE" -lt 100 ]; then
  log "ERREUR: Espace disque peer insuffisant (${PEER_FREE}MB < 100MB) — bascule annulée."
  exit 1
fi
log "  → Espace disque peer OK (${PEER_FREE}MB libres)."

# Peer sans conteneurs actifs ? → les stopper proprement
PEER_CONTAINERS=$($SSH_CMD ptressard@"$PEER_IP" "docker ps -q 2>/dev/null | wc -l" 2>/dev/null || echo 0)
if [ "$PEER_CONTAINERS" -gt 0 ]; then
  log "  ⚠ Peer a $PEER_CONTAINERS conteneur(s) actif(s) — arrêt avant bascule."
  run "$SSH_CMD ptressard@$PEER_IP 'cd /opt/5hostachy && docker compose stop 2>/dev/null'"
fi
log "  → Peer en état standby."

# Poser un lock sur le peer : empêche auto-deploy de relancer les conteneurs pendant la bascule
run "$SSH_CMD ptressard@$PEER_IP 'touch /opt/5hostachy/.bascule-lock'"
log "  → Lock bascule posé sur le peer."

# ── Phase 1 : Sync à chaud (uploads + WA, PAS la DB) ────────────────
log "[1/7] Sync uploads + WhatsApp auth (à chaud)..."

UPL_SRC=$(docker volume inspect 5hostachy_uploads --format '{{.Mountpoint}}')
run "rsync -az --delete -e '$SSH_CMD' '$UPL_SRC/' ptressard@$PEER_IP:/tmp/sync_uploads/"
run "$SSH_CMD ptressard@$PEER_IP 'sudo rsync -a /tmp/sync_uploads/ \$(docker volume inspect 5hostachy_uploads --format \"{{.Mountpoint}}\")/ && rm -rf /tmp/sync_uploads'"
log "  → Uploads synchronisés."

WA_VOL=$(docker volume inspect 5hostachy_whatsapp_auth --format '{{.Mountpoint}}' 2>/dev/null || echo "")
if [ -n "$WA_VOL" ]; then
  run "rsync -az --delete -e '$SSH_CMD' '$WA_VOL/' ptressard@$PEER_IP:/tmp/sync_wa_auth/"
  run "$SSH_CMD ptressard@$PEER_IP 'sudo rsync -a /tmp/sync_wa_auth/ \$(docker volume inspect 5hostachy_whatsapp_auth --format \"{{.Mountpoint}}\")/ && rm -rf /tmp/sync_wa_auth'"
  log "  → WhatsApp auth synchronisé."
fi

# ── Phase 2 : Stop cloudflared local + conteneurs locaux ────────────
# cloudflared LOCAL arrêté EN PREMIER : tant qu'il est actif, les 2 tunnels
# (local + peer, même tunnel ID) coexistent → Cloudflare load-balance ~50/50
# → ~50% des requêtes arrivent sur containers stoppés → 503 pour les vrais users.
# En arrêtant cloudflared ici, un seul tunnel sera actif pendant toute la bascule.
log "[2/7] Arrêt cloudflared local + conteneurs..."
trap 'rollback "2-stop-conteneurs"' ERR
run "sudo systemctl stop cloudflared"
log "  → Cloudflared local stoppé. Plus de trafic public possible jusqu'au peer."
cd "$REPO"
run "docker compose stop"
log "  → Conteneurs arrêtés."

# ── Phase 3 : WAL checkpoint + integrity check DB locale ────────────
log "[3/7] WAL checkpoint + integrity check DB locale..."
trap 'rollback "3-db-locale"' ERR

DB_PATH=$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}')
DB_FILE="$DB_PATH/app.db"

# WAL checkpoint (conteneurs stoppés = 0 writers, garanti complet)
CHKPT=$(sqlite3 "$DB_FILE" "PRAGMA wal_checkpoint(TRUNCATE);" 2>&1)
log "  → WAL checkpoint : $CHKPT"
# Format retour : "busy_count|log_count|checkpointed" — les 3 doivent être cohérents
BUSY=$(echo "$CHKPT" | cut -d'|' -f1)
LOG_CNT=$(echo "$CHKPT" | cut -d'|' -f2)
CKPT_CNT=$(echo "$CHKPT" | cut -d'|' -f3)
if [ "$BUSY" != "0" ]; then
  log "ERREUR: WAL checkpoint incomplet (busy=$BUSY) — bascule annulée."
  false
fi
if [ "$LOG_CNT" != "$CKPT_CNT" ]; then
  log "ERREUR: WAL non entièrement vidé (log=$LOG_CNT, checkpointed=$CKPT_CNT) — bascule annulée."
  false
fi
# Vérifier que le fichier WAL est bien vide (0 octet) après TRUNCATE
WAL_SIZE=$(stat -c%s "${DB_FILE}-wal" 2>/dev/null || echo 0)
if [ "$WAL_SIZE" -gt 0 ]; then
  log "ERREUR: WAL non vide après TRUNCATE (${WAL_SIZE} octets) — bascule annulée."
  false
fi
log "  → WAL vide confirmé (${WAL_SIZE} octets)."

# Integrity check
INTEGRITY=$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;" 2>&1 | head -1)
if [ "$INTEGRITY" != "ok" ]; then
  log "ERREUR: DB locale corrompue ($INTEGRITY) — bascule annulée."
  false
fi
log "  → DB locale OK (integrity: $INTEGRITY)."

# ── Phase 4 : Rsync DB → peer + integrity check sur peer ────────────
log "[4/7] Sync DB → peer + vérification intégrité..."
trap 'rollback "4-sync-db"' ERR

# Sécurité anti-race : re-vérifier que les conteneurs peer sont encore stoppés.
# auto-deploy.sh (cron */5 min) pourrait les avoir relancés entre Phase 0 et maintenant.
if ! $DRY_RUN; then
  PEER_RUNNING=$($SSH_CMD ptressard@"$PEER_IP" "docker ps -q 2>/dev/null | wc -l" 2>/dev/null || echo 0)
  if [ "$PEER_RUNNING" -gt 0 ]; then
    log "  ⚠ Conteneurs peer relancés entretemps ($PEER_RUNNING) — arrêt forcé avant rsync DB."
    $SSH_CMD ptressard@"$PEER_IP" "cd /opt/5hostachy && docker compose stop 2>/dev/null"
    log "  → Conteneurs peer arrêtés."
  fi
fi

# Rsync DB_PATH → /tmp/sync_app_data sur le peer (ptressard, pas besoin de sudo)
# --delete : supprime sur la cible tout fichier absent de la source
#   → nettoie automatiquement les WAL/SHM résiduels du peer (plus besoin de sudo rm)
run "rsync -az --delete -e '$SSH_CMD' '$DB_PATH/' ptressard@$PEER_IP:/tmp/sync_app_data/"
log "  → DB + WAL/SHM synchronisés vers /tmp."

# Integrity check sur /tmp/sync_app_data AVANT de l'installer dans le volume
# → aucun sudo requis (ptressard possède /tmp/sync_app_data)
if ! $DRY_RUN; then
  PEER_INTEGRITY=$($SSH_CMD ptressard@"$PEER_IP" "sqlite3 /tmp/sync_app_data/app.db 'PRAGMA integrity_check;' 2>&1 | head -1" 2>/dev/null || echo "error")
  if [ "$PEER_INTEGRITY" != "ok" ]; then
    log "ERREUR: DB corrompue avant installation sur peer ($PEER_INTEGRITY) — bascule annulée."
    $SSH_CMD ptressard@"$PEER_IP" "rm -rf /tmp/sync_app_data" 2>/dev/null || true
    false
  fi
  log "  → DB OK (integrity: $PEER_INTEGRITY)."
else
  drylog "sqlite3 PRAGMA integrity_check sur /tmp/sync_app_data (sans sudo)"
fi

# Installer DB dans le volume Docker (sudo rsync --delete pour cohérence complète)
run "$SSH_CMD ptressard@$PEER_IP 'sudo rsync -a --delete /tmp/sync_app_data/ \$(docker volume inspect 5hostachy_app_data --format \"{{.Mountpoint}}\")/ && rm -rf /tmp/sync_app_data'"
log "  → DB installée dans le volume peer."

# ── Phase 5 : Start peer + health check API ──────────────────────────
log "[5/7] Démarrage peer + health check API (${HEALTH_TIMEOUT}s max)..."
trap 'rollback "5-start-peer"' ERR

run "$SSH_CMD ptressard@$PEER_IP 'cd /opt/5hostachy && sed -i \"s|^ORIGIN=.*|ORIGIN=https://5hostachy.fr|\" .env && sed -i \"/^COOKIE_SECURE=/d\" .env && docker compose up -d'"
log "  → Conteneurs peer démarrés."

if ! $DRY_RUN; then
  log "  Attente API peer (http://$PEER_IP:8000/health)..."
  API_OK=false
  # L'API n'est pas exposée à l'hôte directement — on passe par docker exec sur le peer
  for i in $(seq 1 $HEALTH_TIMEOUT); do
    STATUS=$($SSH_CMD ptressard@"$PEER_IP" "docker exec hostachy_api curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health 2>/dev/null" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
      API_OK=true
      log "  → API peer OK après ${i}s (HTTP $STATUS)."
      break
    fi
    sleep 1
  done
  if ! $API_OK; then
    log "ERREUR: API peer ne répond pas après ${HEALTH_TIMEOUT}s — bascule annulée."
    false
  fi
else
  drylog "Boucle health check API peer (docker exec hostachy_api curl http://localhost:8000/health)"
fi

# ── Phase 6 : Start cloudflared peer + vérif URL publique ───────────
# cloudflared local déjà arrêté en phase 2 — un seul tunnel actif à la fois.
log "[6/7] Démarrage cloudflared peer + vérification URL publique..."
trap 'rollback "6-cloudflared"' ERR

run "$SSH_CMD ptressard@$PEER_IP 'sudo systemctl start cloudflared'"
log "  → Cloudflared peer démarré. Attente initiale ${CLOUDFLARE_INITIAL_WAIT}s puis polling URL publique (max ${CLOUDFLARE_WAIT}s)..."
run "sleep $CLOUDFLARE_INITIAL_WAIT"

if ! $DRY_RUN; then
  CF_OK=false
  ELAPSED=$CLOUDFLARE_INITIAL_WAIT
  while [ $ELAPSED -lt $CLOUDFLARE_WAIT ]; do
    CF_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "$PUBLIC_URL" 2>/dev/null || echo "000")
    if [ "$CF_STATUS" = "200" ]; then
      CF_OK=true
      log "  → URL publique OK après ${ELAPSED}s (HTTP $CF_STATUS)."
      break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
  done
  if ! $CF_OK; then
    log "ERREUR: URL publique ($PUBLIC_URL) inaccessible après ${CLOUDFLARE_WAIT}s (dernier code: $CF_STATUS) — bascule annulée."
    false
  fi
else
  drylog "Polling URL publique $PUBLIC_URL (${CLOUDFLARE_INITIAL_WAIT}s wait + max ${CLOUDFLARE_WAIT}s polling)"
fi

# ── Phase 7 : MAJ flags ─────────────────────────────────────────────
# cloudflared local déjà arrêté en phase 6 — systemctl stop est idempotent
log "[7/7] Mise à jour flags..."
trap - ERR   # plus de rollback au-delà : l'essentiel est fait

case "$SELF" in
  rpi1) run "sed -i 's|^ORIGIN=.*|ORIGIN=http://192.168.1.222|' $REPO/.env" ;;
  rpi2) run "sed -i 's|^ORIGIN=.*|ORIGIN=http://192.168.1.223|' $REPO/.env" ;;
esac
grep -q '^COOKIE_SECURE=' "$REPO/.env" || echo 'COOKIE_SECURE=false' >> "$REPO/.env"

run "echo $PEER > $FLAG"
run "$SSH_CMD ptressard@$PEER_IP 'echo $PEER > /opt/5hostachy/.active'"

# Supprimer le lock bascule sur le peer (la bascule est terminée)
run "$SSH_CMD ptressard@$PEER_IP 'rm -f /opt/5hostachy/.bascule-lock'"
log "  → Lock bascule supprimé sur le peer."

log "===== Bascule terminée : $PEER est maintenant actif ====="
