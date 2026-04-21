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
