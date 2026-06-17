#!/bin/bash
# =============================================================================
#  health-watch.sh — Surveillance site 5Hostachy + reprise automatique
#
#  Tourne toutes les 5 min sur les DEUX RPi via cron.
#  Si l'URL publique ne répond plus :
#    - RPi actif   → redémarre ses propres conteneurs + cloudflared
#    - RPi standby → prend le relais (failover) + démarre conteneurs + cloudflared
#  Envoie un email d'alerte dans tous les cas (via Python3 standalone).
#
#  Cron (sudo crontab sur chaque RPi) :
#    */5 * * * * /opt/5hostachy/health-watch.sh >> /var/log/hostachy-health-watch.log 2>&1
# =============================================================================
set -uo pipefail

REPO=/opt/5hostachy
PUBLIC_URL="https://5hostachy.fr/api/health"
ALERT_EMAIL="ptressard@icloud.com"
COOLDOWN_FILE="/tmp/health-watch-cooldown"
COOLDOWN_SECONDS=1800   # 30 min entre deux alertes email pour éviter le spam

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# ── Identité de ce RPi ───────────────────────────────────────────────────────
CUR_HOSTNAME=$(hostname)
case "$CUR_HOSTNAME" in
  PhT-RB5)   SELF="rpi1" ;;
  PhT-RB5i2) SELF="rpi2" ;;
  *) log "Hostname inconnu ($CUR_HOSTNAME) — abandon."; exit 1 ;;
esac

# ── Verrou anti-concurrence — robuste ────────────────────────────────────────
# Historique : un /tmp/health-watch.lock créé par un autre utilisateur (run manuel
# vs cron root) rendait `exec 9>` impossible → "Permission denied" + "flock: 9:
# Bad file descriptor" en boucle. On tente le lock partagé, puis on retombe sur un
# lock par utilisateur, et on n'avorte JAMAIS le script à cause du seul verrou.
LOCK_FILE="/tmp/health-watch.lock"
if ! exec 9>"$LOCK_FILE" 2>/dev/null; then
    LOCK_FILE="/tmp/health-watch-${SELF}-$(id -u).lock"
    exec 9>"$LOCK_FILE" 2>/dev/null || { log "Verrou inaccessible ($LOCK_FILE) — abandon."; exit 0; }
fi
chmod 666 "$LOCK_FILE" 2>/dev/null || true   # accessible root ET ptressard pour les prochains runs
flock -n 9 || { log "Autre instance en cours — abandon."; exit 0; }

# ── Check URL publique ────────────────────────────────────────────────────────
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$PUBLIC_URL" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
    # Site OK — supprimer le cooldown si présent (reset pour la prochaine panne)
    rm -f "$COOLDOWN_FILE"
    exit 0
fi

log "⚠ Site HS (HTTP $HTTP_CODE) — RPi: $SELF"

# ── Identité du RPi actif ─────────────────────────────────────────────────────
FLAG="$REPO/.active"
ACTIVE=$(cat "$FLAG" 2>/dev/null | tr -d '[:space:]' || echo "")

# ── Cooldown email (évite le spam si la panne dure) ──────────────────────────
send_email() {
    local subject="$1"
    local body="$2"

    # Lire config mail depuis .env
    MAIL_SERVER=$(grep -E '^MAIL_SERVER=' "$REPO/.env" | cut -d= -f2- | tr -d '"')
    MAIL_PORT=$(grep -E '^MAIL_PORT=' "$REPO/.env" | cut -d= -f2- | tr -d '"')
    MAIL_USERNAME=$(grep -E '^MAIL_USERNAME=' "$REPO/.env" | cut -d= -f2- | tr -d '"')
    MAIL_PASSWORD=$(grep -E '^MAIL_PASSWORD=' "$REPO/.env" | cut -d= -f2- | tr -d '"')
    MAIL_FROM=$(grep -E '^MAIL_FROM=' "$REPO/.env" | cut -d= -f2- | tr -d '"')

    python3 - "$subject" "$body" "$MAIL_SERVER" "$MAIL_PORT" "$MAIL_USERNAME" "$MAIL_PASSWORD" "$MAIL_FROM" "$ALERT_EMAIL" <<'PYEOF'
import sys, smtplib
from email.mime.text import MIMEText
subject, body, server, port, user, password, from_addr, to_addr = sys.argv[1:]
msg = MIMEText(body)
msg['Subject'] = subject
msg['From'] = from_addr
msg['To'] = to_addr
try:
    s = smtplib.SMTP(server, int(port))
    s.starttls()
    s.login(user, password)
    s.sendmail(from_addr, [to_addr], msg.as_string())
    s.quit()
    print("Email envoyé.")
except Exception as e:
    print(f"Email KO: {e}")
PYEOF
}

alert_if_not_in_cooldown() {
    local subject="$1"
    local body="$2"
    local now
    now=$(date +%s)

    if [ -f "$COOLDOWN_FILE" ]; then
        local last_sent
        last_sent=$(cat "$COOLDOWN_FILE")
        local elapsed=$(( now - last_sent ))
        if [ "$elapsed" -lt "$COOLDOWN_SECONDS" ]; then
            log "  Email en cooldown (envoyé il y a ${elapsed}s, attente ${COOLDOWN_SECONDS}s) — skipped."
            return
        fi
    fi

    send_email "$subject" "$body" && echo "$now" > "$COOLDOWN_FILE"
}

# ── Bascule OU déploiement en cours ? Éviter d'interférer ────────────────────
# .bascule-lock est posé par bascule.sh ET par MaJ-Hostachy.sh : pendant un
# déploiement, l'API est brièvement down (rebuild) → sans ce garde-fou le standby
# basculait et créait un split-brain (incident du 17/06/2026).
if [ -f "$REPO/.bascule-lock" ]; then
    log "  Bascule/déploiement en cours (.bascule-lock présent) — pas d'intervention."
    exit 0
fi

# ── Ce RPi est-il le standby ? ───────────────────────────────────────────────
# Seul le standby surveille et bascule. Si ce RPi est l'actif et qu'il peut
# encore exécuter ce script, le problème vient d'ailleurs (réseau, Cloudflare)
# et non d'un freeze — on laisse Docker restart: unless-stopped gérer ça.
if [ "$ACTIVE" = "$SELF" ]; then
    log "  Ce RPi ($SELF) est l'actif — pas d'intervention (surveillance assurée par le standby)."
    exit 0
fi

# ── Double vérification (évite les faux positifs sur coupure réseau courte) ──
log "  Standby $SELF surveille. Vérification secondaire dans 30s..."
sleep 30
# Re-tester le lock de bascule/déploiement : il a pu être posé pendant l'attente.
if [ -f "$REPO/.bascule-lock" ]; then
    log "  Bascule/déploiement détecté pendant l'attente — pas d'intervention."
    exit 0
fi
HTTP_CODE2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$PUBLIC_URL" 2>/dev/null || echo "000")
if [ "$HTTP_CODE2" = "200" ]; then
    log "  Site revenu entre les deux checks (HTTP $HTTP_CODE2) — faux positif, pas d'action."
    exit 0
fi
log "  Confirmation panne (HTTP $HTTP_CODE2) — failover vers $SELF."

# ── Failover : ce RPi standby prend le relais ────────────────────────────────
cd "$REPO"

# Poser le lock pour éviter qu'une bascule cron se déclenche en parallèle
touch "$REPO/.bascule-lock"
trap 'rm -f "$REPO/.bascule-lock"' EXIT

sed -i "s|^ORIGIN=.*|ORIGIN=https://5hostachy.fr|" "$REPO/.env"
sed -i "/^COOKIE_SECURE=/d" "$REPO/.env"

docker compose up -d >> /dev/null 2>&1 && log "  → Conteneurs $SELF démarrés." || log "  ⚠ Échec démarrage conteneurs."
sudo systemctl start cloudflared 2>/dev/null && log "  → Cloudflared $SELF démarré." || log "  ⚠ Échec démarrage cloudflared."

echo "$SELF" > "$FLAG"
log "  → Flag actif mis à jour : $SELF"

# Re-check après failover
sleep 20
HTTP_AFTER=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$PUBLIC_URL" 2>/dev/null || echo "000")

if [ "$HTTP_AFTER" = "200" ]; then
    log "  ✅ Failover réussi — $SELF est maintenant actif (HTTP 200)."
    alert_if_not_in_cooldown \
        "[5Hostachy] ⚠ Failover automatique : $ACTIVE HS → $SELF actif" \
        "Le RPi actif ($ACTIVE) ne répondait plus.
Failover automatique effectué vers $SELF.

Le site répond à nouveau (HTTP 200).
La base de données est celle de $SELF au moment du failover (sans sync depuis $ACTIVE).

Action recommandée dès que $ACTIVE est de retour :
  Vérifier les données et relancer une bascule manuelle.

Date : $(date '+%d/%m/%Y à %H:%M')"
else
    log "  ❌ Failover échoué — site toujours HS (HTTP $HTTP_AFTER)."
    alert_if_not_in_cooldown \
        "[5Hostachy] ❌ Site HS — failover échoué ($ACTIVE et $SELF inopérants)" \
        "Le site ne répond plus (HTTP $HTTP_AFTER).
Le RPi actif ($ACTIVE) est HS et la tentative de failover vers $SELF a aussi échoué.

Intervention manuelle requise sur les deux machines.

Date : $(date '+%d/%m/%Y à %H:%M')"
fi
