#!/bin/bash
# auto-deploy.sh — Synchronisation automatique git + rebuild si changements
set -euo pipefail
REPO=/opt/5hostachy
LOG_DATE=$(date '+%Y-%m-%d %H:%M:%S')
cd "$REPO"

# Ne pas déployer si une bascule est en cours (évite race condition DB)
if [ -f "$REPO/.bascule-lock" ]; then
    echo "[$LOG_DATE] Bascule en cours — auto-deploy ignoré."
    exit 0
fi

# Garde actif/standby : ne déployer QUE sur le RPi actif. `docker compose up -d` sur le
# standby = split-brain. Avec ce garde, le cron peut tourner sur les 2 RPi sans risque
# (failover-proof) — sinon le cron reste figé sur l'ancien actif après un failover et soit
# ne déploie plus (nouvel actif), soit split-brain (ancien actif devenu standby). Cf 23/06/2026.
case "$(hostname)" in
    PhT-RB5)   SELF=rpi1 ;;
    PhT-RB5i2) SELF=rpi2 ;;
    *) echo "[$LOG_DATE] Hostname inconnu ($(hostname)) — auto-deploy ignoré."; exit 0 ;;
esac
ACTIVE=$(cat "$REPO/.active" 2>/dev/null | tr -d '[:space:]')
if [ -n "$ACTIVE" ] && [ "$ACTIVE" != "$SELF" ]; then
    echo "[$LOG_DATE] $SELF n'est pas l'actif ($ACTIVE) — auto-deploy ignoré (anti-split-brain)."
    exit 0
fi

git fetch origin main --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[$LOG_DATE] Changements détectés, déploiement..."
    git reset --hard origin/main
    export GIT_HASH=$(git rev-parse --short HEAD)
    docker compose build --quiet
    docker compose up -d
    sleep 5
    docker exec hostachy_api sh -lc 'cd /app && alembic upgrade head' 2>/dev/null || true
    echo "[$LOG_DATE] Déployé: $GIT_HASH"
fi
