#!/bin/bash
# =============================================================================
#  lib-alert.sh — Envoi d'alertes e-mail avec cooldown (module à sourcer)
#
#  POURQUOI ce module existe (incident du 26/07/2026) :
#    `check-reliability.sh` (cron */15) a détecté l'incohérence de `.active`
#    NEUF FOIS d'affilée — `[FAIL] .active divergent — rpi2='rpi2' vs rpi1='rpi1'`
#    de 06:53 à 09:28 — pendant que le failover était neutralisé et le site HS
#    ~50 min. Personne ne l'a su : le cron redirige toute la sortie vers
#    /var/log/hostachy-reliability.log, donc `MAILTO` ne reçoit rien, et le script
#    n'avait aucun canal d'alerte propre. La détection marchait ; c'est la
#    NOTIFICATION qui manquait.
#
#  Le mécanisme SMTP était écrit en dur dans health-watch.sh. Il est factorisé ici
#  pour que tout script d'infra puisse alerter sans le recopier (règle de
#  non-duplication du projet).
#
#  Usage :
#    source /opt/5hostachy/lib-alert.sh
#    ALERT_COOLDOWN_FILE=/tmp/mon-script-cooldown   # défaut : par nom de script
#    ALERT_COOLDOWN_SECONDS=3600                    # défaut : 1800 (30 min)
#    alert_if_not_in_cooldown "sujet" "corps"
#
#  Le cooldown évite le spam quand une panne dure (à */15, un FAIL persistant
#  produirait 96 e-mails par jour).
#
#  ⚠ Limite connue : canal UNIQUE (SMTP). Il tombe avec le réseau, donc
#  précisément quand on en a besoin — le 26/07, health-watch a loggué
#  « Email KO: [Errno 101] Network is unreachable ». Un second canal
#  (WhatsApp via le bridge, ou heartbeat sortant) reste à ajouter.
# =============================================================================

ALERT_EMAIL="${ALERT_EMAIL:-ptressard@icloud.com}"
ALERT_REPO="${ALERT_REPO:-/opt/5hostachy}"
ALERT_COOLDOWN_SECONDS="${ALERT_COOLDOWN_SECONDS:-1800}"
ALERT_COOLDOWN_FILE="${ALERT_COOLDOWN_FILE:-/tmp/alert-cooldown-$(basename "${0%.sh}")}"

# Journalisation : réutilise le log() du script appelant s'il en définit un.
if ! declare -f log >/dev/null 2>&1; then
    log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fi

alert_send_email() {
    local subject="$1" body="$2"

    local server port username password from
    server=$(grep -E '^MAIL_SERVER='   "$ALERT_REPO/.env" | cut -d= -f2- | tr -d '"')
    port=$(grep -E '^MAIL_PORT='       "$ALERT_REPO/.env" | cut -d= -f2- | tr -d '"')
    username=$(grep -E '^MAIL_USERNAME=' "$ALERT_REPO/.env" | cut -d= -f2- | tr -d '"')
    password=$(grep -E '^MAIL_PASSWORD=' "$ALERT_REPO/.env" | cut -d= -f2- | tr -d '"')
    from=$(grep -E '^MAIL_FROM='       "$ALERT_REPO/.env" | cut -d= -f2- | tr -d '"')

    if [ -z "$server" ] || [ -z "$username" ]; then
        log "  ⚠ Alerte non envoyée : SMTP non configuré dans $ALERT_REPO/.env."
        return 1
    fi

    python3 - "$subject" "$body" "$server" "$port" "$username" "$password" "$from" "$ALERT_EMAIL" <<'PYEOF'
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
    raise SystemExit(1)
PYEOF
}

alert_if_not_in_cooldown() {
    local subject="$1" body="$2"
    local now last elapsed
    now=$(date +%s)

    if [ -f "$ALERT_COOLDOWN_FILE" ]; then
        last=$(cat "$ALERT_COOLDOWN_FILE" 2>/dev/null || echo 0)
        elapsed=$(( now - ${last:-0} ))
        if [ "$elapsed" -lt "$ALERT_COOLDOWN_SECONDS" ]; then
            log "  Alerte en cooldown (envoyée il y a ${elapsed}s / ${ALERT_COOLDOWN_SECONDS}s) — non renvoyée."
            return 0
        fi
    fi

    if alert_send_email "$subject" "$body"; then
        echo "$now" > "$ALERT_COOLDOWN_FILE"
        log "  Alerte envoyée à $ALERT_EMAIL."
    else
        # Pas de mise à jour du cooldown : on retentera au prochain passage.
        log "  ⚠ Échec d'envoi de l'alerte — nouvelle tentative au prochain cycle."
    fi
}
