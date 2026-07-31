#!/bin/bash
# auto-deploy.sh — Synchronisation automatique git + rebuild si changements
#
# CONTRAT DE BATTEMENT : tout chemin de sortie écrit UNE ligne horodatée
# `[AAAA-MM-JJ HH:MM:SS] …` dans le log. check-reliability (C14) ne lit rien
# d'autre : la date de la dernière ligne est l'heure du dernier run mené à
# terme. Un chemin muet = un script réputé mort. Ne pas ajouter de `exit`
# sans sa ligne datée.
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
source "$REPO/lib-role.sh"
SELF=$(role_of "$(hostname)")
if [ -z "$SELF" ]; then
    echo "[$LOG_DATE] Hostname inconnu ($(hostname)) — auto-deploy ignoré."
    exit 0
fi
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
else
    # Cas le plus fréquent sur l'actif. Il était MUET jusqu'au 31/07/2026 : le log
    # ne bougeait plus des heures durant sans que rien n'aille mal, donc l'absence
    # de battement ne pouvait pas non plus signaler une panne — c'est exactement
    # ainsi qu'auto-deploy est resté KO 7 semaines sur rpi1 (bit x perdu, 21/04).
    echo "[$LOG_DATE] Aucun changement ($(git rev-parse --short HEAD)) — rien à déployer."
fi
