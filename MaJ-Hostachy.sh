#!/bin/bash
# ============================================================
#  MaJ-Hostachy.sh — Mise à jour de l'application
#  Usage : bash /opt/5hostachy/MaJ-Hostachy.sh [--nocache]
#  --nocache : build complet sans cache Docker (utile si
#              dépendances corrompues, base image à rafraîchir,
#              ou comportement inexpliqué)
#  Sans flag  : build sélectif + cache Docker (rapide ~1-2 min)
# ============================================================
set -e

REPO=/opt/5hostachy
LOG_DATE=$(date '+%Y-%m-%d %H:%M:%S')
NO_CACHE=false

for arg in "$@"; do
    case "$arg" in
        --nocache) NO_CACHE=true ;;
    esac
done

if $NO_CACHE; then
    echo "[$LOG_DATE] === Mise à jour Hostachy (mode --nocache : build complet) ==="
else
    echo "[$LOG_DATE] === Mise à jour Hostachy (build sélectif + cache) ==="
fi

# 1. Synchronisation git
cd "$REPO"
echo "[$LOG_DATE] Récupération des derniers commits depuis GitHub..."
git fetch origin main
# reset --hard : force la synchro avec GitHub (fichiers non trackés comme .env sont préservés)
# En cas de modifications locales sur des fichiers trackés, elles seront écrasées
git reset --hard origin/main
echo "[$LOG_DATE] Code synchronisé : $(git log --oneline -1)"

# 1b. Synchronisation manuel utilisateur
# Filet de sécurité : si docs/ et front/static/ divergent (oubli de commit côté dev),
# on prend docs/ comme source de vérité avant le rebuild du frontend.
if ! diff -q "$REPO/docs/manuel-utilisateur.html" "$REPO/front/static/manuel-utilisateur.html" > /dev/null 2>&1; then
    echo "[$LOG_DATE] ⚠️  manuel-utilisateur.html désynchronisé — copie de docs/ → front/static/"
    cp "$REPO/docs/manuel-utilisateur.html" "$REPO/front/static/manuel-utilisateur.html"
else
    echo "[$LOG_DATE] Manuel utilisateur synchronisé ✓"
fi

if [ -f "$REPO/docs/manuel-utilisateur-1-page.html" ]; then
    if ! diff -q "$REPO/docs/manuel-utilisateur-1-page.html" "$REPO/front/static/manuel-utilisateur-1-page.html" > /dev/null 2>&1; then
        echo "[$LOG_DATE] ⚠️  manuel-utilisateur-1-page.html désynchronisé — copie de docs/ → front/static/"
        cp "$REPO/docs/manuel-utilisateur-1-page.html" "$REPO/front/static/manuel-utilisateur-1-page.html"
    else
        echo "[$LOG_DATE] Manuel utilisateur 1 page synchronisé ✓"
    fi
fi

# 1c. Synchronisation images du manuel utilisateur
if [ -d "$REPO/docs/img" ]; then
    mkdir -p "$REPO/front/static/img"
    rsync -a --delete "$REPO/docs/img/" "$REPO/front/static/img/"
    echo "[$LOG_DATE] Images manuel utilisateur synchronisées ✓"
fi

# 2. Rebuild et redémarrage des conteneurs
GIT_HASH=$(git rev-parse --short HEAD)
export GIT_HASH
PREV_HASH=$(docker inspect --format '{{index .Config.Labels "git.hash"}}' hostachy_front 2>/dev/null || echo "")

if $NO_CACHE; then
    # --- Mode --nocache : rebuild total sans cache ---
    echo "[$LOG_DATE] Build complet sans cache + force-recreate..."
    docker compose -f "$REPO/docker-compose.yml" build --no-cache
    docker compose -f "$REPO/docker-compose.yml" up --force-recreate -d
else
    # --- Mode normal : build sélectif ---
    CHANGED_DIRS=$(git diff --name-only "$PREV_HASH" HEAD 2>/dev/null | cut -d/ -f1 | sort -u)
    SERVICES_TO_BUILD=""

    for dir in $CHANGED_DIRS; do
        case "$dir" in
            front)            SERVICES_TO_BUILD="$SERVICES_TO_BUILD front" ;;
            api)              SERVICES_TO_BUILD="$SERVICES_TO_BUILD api" ;;
            whatsapp-bridge)  SERVICES_TO_BUILD="$SERVICES_TO_BUILD whatsapp-bridge" ;;
        esac
    done
    # Dédoublonner
    SERVICES_TO_BUILD=$(echo "$SERVICES_TO_BUILD" | tr ' ' '\n' | sort -u | tr '\n' ' ' | xargs)

    # Fichiers racine modifiés (docker-compose, Caddyfile…) → tout rebuild
    ROOT_FILES=$(git diff --name-only "$PREV_HASH" HEAD 2>/dev/null | grep -cE '^(docker-compose\.yml|Caddyfile)$' || true)
    if [ -z "$PREV_HASH" ] || [ -z "$SERVICES_TO_BUILD" ] || [ "$ROOT_FILES" -gt 0 ]; then
        SERVICES_TO_BUILD="front api whatsapp-bridge"
    fi

    echo "[$LOG_DATE] Services à rebuild : $SERVICES_TO_BUILD"
    docker compose -f "$REPO/docker-compose.yml" build $SERVICES_TO_BUILD
    docker compose -f "$REPO/docker-compose.yml" up -d
fi

# 3. Attendre que l'API soit prête
echo "[$LOG_DATE] Attente du démarrage de l'API..."
for i in $(seq 1 15); do
    if docker exec hostachy_api curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "[$LOG_DATE] API opérationnelle."
        break
    fi
    sleep 2
done

# 3b. Appliquer les migrations DB (sécurité post-déploiement)
echo "[$LOG_DATE] Application des migrations Alembic..."
docker exec hostachy_api sh -lc "cd /app && alembic upgrade head"
echo "[$LOG_DATE] Migrations Alembic appliquées ✓"

# 4. Résumé
echo ""
echo "[$LOG_DATE] === État des conteneurs ==="
docker compose -f "$REPO/docker-compose.yml" ps
echo "[$LOG_DATE] === Logs récents de l'API ==="
docker logs hostachy_api --tail 10
echo "[$LOG_DATE] === Mise à jour terminée ==="
