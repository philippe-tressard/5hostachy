#!/bin/bash
# =============================================================================
#  maintenance.sh — Maintenance automatique 5Hostachy
#
#  Tâches :
#    - Purge des refresh tokens expirés/révoqués  (mensuel, 1er du mois)
#    - VACUUM SQLite                               (mensuel, 1er du mois)
#    - Nettoyage images Docker inutilisées         (mensuel, 1er du mois)
#    - Nettoyage des logs WhatsApp (6 derniers)   (mensuel, 1er du mois)
#    - Nettoyage des évolutions archivées (>90j)  (mensuel, 1er du mois)
#
#  Installation cron (en tant que root sur le RPi) :
#    sudo crontab -e
#    # Lancer tous les 1er du mois à 03:00
#    0 3 1 * * /opt/5hostachy/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
#
#  Lancement manuel (via SSH root) :
#    /opt/5hostachy/maintenance.sh
#
#  Prérequis .env :
#    MAINTENANCE_KEY=<clé aléatoire identique dans .env API>
# =============================================================================
set -euo pipefail

REPO=/opt/5hostachy
MAINTE_START=$SECONDS
MAINTE_DEBUT=$(date -u +%Y-%m-%dT%H:%M:%S)
GLOBAL_STATUT="succes"
GLOBAL_ERREUR=""

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log ""
log "===== Maintenance Hostachy ====="

# --- 1. Purge refresh tokens expirés / révoqués --------------------------------
log "[1/3] Purge des refresh tokens expirés/révoqués..."
MAINT_ERR=$(mktemp)
DELETED=$(docker exec hostachy_api python -c "
from app.database import engine
from sqlalchemy import text
from datetime import datetime, timezone
with engine.connect() as c:
    r = c.execute(
        text('DELETE FROM refresh_token WHERE expires_at < :now OR revoked = 1'),
        {'now': datetime.now(timezone.utc).isoformat()}
    )
    c.commit()
    print(r.rowcount)
" 2>"$MAINT_ERR") || {
    ERREUR_DETAIL=$(cat "$MAINT_ERR")
    log "ERREUR purge tokens : $ERREUR_DETAIL"
    GLOBAL_STATUT="erreur"
    GLOBAL_ERREUR="purge tokens: $ERREUR_DETAIL"
    DELETED=0
}
rm -f "$MAINT_ERR"
log "  → $DELETED token(s) supprimé(s)"

# --- 2. VACUUM SQLite ----------------------------------------------------------
# VACUUM ne peut pas s'exécuter dans une transaction : isolation_level AUTOCOMMIT obligatoire
log "[2/3] VACUUM SQLite..."
MAINT_ERR2=$(mktemp)
docker exec hostachy_api python -c "
from app.database import engine
from sqlalchemy import text
from datetime import datetime, timedelta, timezone

with engine.execution_options(isolation_level='AUTOCOMMIT').connect() as c:
    c.execute(text('VACUUM'))
    print('OK')
    
    # Nettoyage des logs WhatsApp anciens (garder seulement 6 messages)
    from app.models.core import WhatsAppLog
    from sqlmodel import Session, select
    with Session(engine) as s:
        all_logs = s.exec(select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())).all()
        if len(all_logs) > 6:
            for old in all_logs[6:]:
                s.delete(old)
            s.commit()
    
    # Nettoyage des évolutions de publications anciennes (archivage après 90 jours)
    from app.models.core import PublicationEvolution
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    with Session(engine) as s:
        old_evols = s.exec(
            select(PublicationEvolution).where(PublicationEvolution.cree_le < cutoff)
        ).all()
        for evol in old_evols:
            s.delete(evol)
        if old_evols:
            s.commit()
" 2>"$MAINT_ERR2" \
    && log "  → VACUUM et nettoyage complétés" \
    || {
        ERREUR_VACUUM=$(cat "$MAINT_ERR2")
        log "  ERREUR VACUUM : $ERREUR_VACUUM"
        GLOBAL_STATUT="erreur"
        GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }VACUUM: $ERREUR_VACUUM"
    }
rm -f "$MAINT_ERR2"

# --- Taille DB après VACUUM ---------------------------------------------------
DB_SIZE=$(docker exec hostachy_api python -c \
    "import os; print(os.path.getsize('/app/data/app.db'))" 2>/dev/null) \
    || DB_SIZE="null"

# --- 3. Nettoyage images Docker inutilisées ------------------------------------
log "[3/3] Nettoyage images Docker inutilisées..."
PRUNE_OUT=$(docker image prune -f 2>&1 | tail -1) || PRUNE_OUT="(docker image prune échoué)"
log "  → $PRUNE_OUT"

# --- Enregistrement dans l'API ------------------------------------------------
MAINTE_FIN=$(date -u +%Y-%m-%dT%H:%M:%S)
DUREE=$(( SECONDS - MAINTE_START ))
MAINTENANCE_KEY=$(grep -E '^MAINTENANCE_KEY=' "$REPO/.env" 2>/dev/null \
    | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'") || MAINTENANCE_KEY=""

if [ -n "$MAINTENANCE_KEY" ]; then
    ERREUR_JSON=$(echo "$GLOBAL_ERREUR" | sed 's/"/\\"/g')
    PAYLOAD=$(printf \
        '{"statut":"%s","tokens_supprimes":%s,"taille_db_octets":%s,"duree_secondes":%d,"erreur":"%s","cree_le":"%s","terminee_le":"%s"}' \
        "$GLOBAL_STATUT" "$DELETED" "$DB_SIZE" "$DUREE" "$ERREUR_JSON" "$MAINTE_DEBUT" "$MAINTE_FIN")
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST http://localhost/api/admin/maintenance/rapport \
        -H "Content-Type: application/json" \
        -H "x-maintenance-key: $MAINTENANCE_KEY" \
        -d "$PAYLOAD" 2>/dev/null) || HTTP_CODE="000"
    if [ "$HTTP_CODE" = "201" ]; then
        log "  → Rapport enregistré (HTTP $HTTP_CODE)"
    else
        log "  ⚠ Rapport non enregistré (HTTP $HTTP_CODE)"
    fi
else
    log "  ⚠ MAINTENANCE_KEY absent du .env — rapport non enregistré"
fi

log "===== Maintenance terminée (${DUREE}s, statut: $GLOBAL_STATUT) ====="
