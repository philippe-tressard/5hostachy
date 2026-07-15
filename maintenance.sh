#!/bin/bash
# =============================================================================
#  maintenance.sh — Maintenance automatique 5Hostachy
#
#  Tâches :
#    - Purge des refresh tokens expirés/révoqués  (hebdomadaire, dimanche)
#    - Purge des password reset tokens expirés     (hebdomadaire, dimanche)
#    - Purge des notifications lues > 90 jours     (hebdomadaire, dimanche)
#    - Purge des rapports de maintenance > 12 mois (hebdomadaire, dimanche)
#    - Purge de l'historique emails > 90 jours     (hebdomadaire, dimanche)
#    - VACUUM SQLite                               (hebdomadaire, dimanche)
#    - Nettoyage des logs WhatsApp (6 derniers)   (hebdomadaire, dimanche)
#    - Nettoyage des évolutions archivées (>90j)  (hebdomadaire, dimanche)
#    - Nettoyage images Docker inutilisées         (hebdomadaire, dimanche)
#
#  Installation cron (en tant que root sur le RPi) :
#    sudo crontab -e
#    # Lancer chaque dimanche à 03:00
#    0 3 * * 0 /opt/5hostachy/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
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

# --- Vérification : ce RPi est-il le RPi actif ? ------------------------------
FLAG="$REPO/.active"
if [ -f "$FLAG" ]; then
    HOSTNAME=$(hostname)
    case "$HOSTNAME" in
      PhT-RB5)   SELF="rpi1" ;;
      PhT-RB5i2) SELF="rpi2" ;;
      *)         SELF="" ;;
    esac
    ACTIVE=$(cat "$FLAG" | tr -d '[:space:]')
    if [ -n "$SELF" ] && [ "$ACTIVE" != "$SELF" ]; then
        log "Ce RPi ($SELF) n'est pas actif ($ACTIVE) — maintenance ignorée."
        exit 0
    fi
fi

log ""
log "===== Maintenance Hostachy ====="

# --- 0. Vérification espace disque (alerte si < 10 %) -------------------------
log "[0/5] Vérification espace disque..."
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
DISK_FREE=$((100 - DISK_USAGE))
DISK_TOTAL=$(df -h / | awk 'NR==2 {print $2}')
DISK_AVAIL=$(df -h / | awk 'NR==2 {print $4}')
log "  → Espace disque : ${DISK_FREE}% libre (${DISK_AVAIL} sur ${DISK_TOTAL})"

if [ "$DISK_FREE" -lt 10 ]; then
    log "  ⚠ ALERTE : espace disque faible (${DISK_FREE}% libre)"
    # Envoi d'alerte email via l'API (template alerte_espace_disque)
    docker exec hostachy_api python -c "
import asyncio
from app.utils.email import send_email, get_site_manager_notification_email
from app.database import SessionLocal
session = SessionLocal()
to, cfg = get_site_manager_notification_email(session)
if to:
    asyncio.run(send_email(
        'alerte_espace_disque', to,
        {'pourcentage_libre': '${DISK_FREE}', 'espace_disponible': '${DISK_AVAIL}', 'espace_total': '${DISK_TOTAL}'},
        session,
    ))
session.close()
" 2>/dev/null || log "  ⚠ Échec envoi alerte email espace disque"
fi

# --- 1. Purge refresh tokens expirés / révoqués --------------------------------
log "[1/5] Purge des refresh tokens expirés/révoqués..."
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

# --- 1b. Purge password reset tokens expirés/utilisés --------------------------
log "[1b/5] Purge des password reset tokens expirés/utilisés..."
MAINT_ERR1B=$(mktemp)
DELETED_PRT=$(docker exec hostachy_api python -c "
from app.database import engine
from sqlalchemy import text
from datetime import datetime, timezone
with engine.connect() as c:
    r = c.execute(
        text('DELETE FROM password_reset_token WHERE expires_at < :now OR used = 1'),
        {'now': datetime.now(timezone.utc).isoformat()}
    )
    c.commit()
    print(r.rowcount)
" 2>"$MAINT_ERR1B") || {
    ERREUR_DETAIL=$(cat "$MAINT_ERR1B")
    log "ERREUR purge password reset tokens : $ERREUR_DETAIL"
    GLOBAL_STATUT="erreur"
    GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }purge prt: $ERREUR_DETAIL"
    DELETED_PRT=0
}
rm -f "$MAINT_ERR1B"
log "  → $DELETED_PRT password reset token(s) supprimé(s)"

# --- 1c. Purge notifications lues > 90 jours -----------------------------------
log "[1c/5] Purge des notifications lues > 90 jours..."
MAINT_ERR1C=$(mktemp)
DELETED_NOTIF=$(docker exec hostachy_api python -c "
from app.database import engine
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
with engine.connect() as c:
    r = c.execute(
        text('DELETE FROM notification WHERE lue = 1 AND cree_le < :cutoff'),
        {'cutoff': cutoff}
    )
    c.commit()
    print(r.rowcount)
" 2>"$MAINT_ERR1C") || {
    ERREUR_DETAIL=$(cat "$MAINT_ERR1C")
    log "ERREUR purge notifications : $ERREUR_DETAIL"
    GLOBAL_STATUT="erreur"
    GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }purge notif: $ERREUR_DETAIL"
    DELETED_NOTIF=0
}
rm -f "$MAINT_ERR1C"
log "  → $DELETED_NOTIF notification(s) supprimée(s)"

# --- 1d. Purge rapports de maintenance > 12 mois -------------------------------
log "[1d/5] Purge historique maintenance > 12 mois..."
MAINT_ERR1D=$(mktemp)
DELETED_HIST=$(docker exec hostachy_api python -c "
from app.database import engine
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
with engine.connect() as c:
    r = c.execute(
        text('DELETE FROM historique_maintenance WHERE cree_le < :cutoff'),
        {'cutoff': cutoff}
    )
    c.commit()
    print(r.rowcount)
" 2>"$MAINT_ERR1D") || {
    ERREUR_DETAIL=$(cat "$MAINT_ERR1D")
    log "ERREUR purge historique : $ERREUR_DETAIL"
    GLOBAL_STATUT="erreur"
    GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }purge hist: $ERREUR_DETAIL"
    DELETED_HIST=0
}
rm -f "$MAINT_ERR1D"
log "  → $DELETED_HIST rapport(s) supprimé(s)"

# --- 1e. Purge historique emails > 90 jours ------------------------------------
log "[1e/5] Purge historique emails (>90 jours)..."
MAINT_ERR1E=$(mktemp)
DELETED_EMAILS=$(docker exec hostachy_api python -c "
from app.database import engine
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
cutoff = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
with engine.connect() as c:
    r = c.execute(
        text('DELETE FROM historique_email WHERE cree_le < :cutoff'),
        {'cutoff': cutoff}
    )
    c.commit()
    print(r.rowcount)
" 2>"$MAINT_ERR1E") || {
    ERREUR_DETAIL=$(cat "$MAINT_ERR1E")
    log "ERREUR purge historique emails : $ERREUR_DETAIL"
    GLOBAL_STATUT="erreur"
    GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }purge hist emails: $ERREUR_DETAIL"
    DELETED_EMAILS=0
}
rm -f "$MAINT_ERR1E"
log "  → $DELETED_EMAILS entrée(s) supprimée(s)"

# --- 2. Nettoyages applicatifs (API live — DELETE multi-process = sûr en WAL) ---
log "[2/5] Nettoyages applicatifs (logs WhatsApp, évolutions archivées >90j)..."
MAINT_ERR2=$(mktemp)
docker exec hostachy_api python -c "
from app.database import engine
from datetime import datetime, timedelta, timezone
from app.models.core import WhatsAppLog, PublicationEvolution
from sqlmodel import Session, select
with Session(engine) as s:
    all_logs = s.exec(select(WhatsAppLog).order_by(WhatsAppLog.envoye_le.desc())).all()
    for old in all_logs[6:]:
        s.delete(old)
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for evol in s.exec(select(PublicationEvolution).where(PublicationEvolution.cree_le < cutoff)).all():
        s.delete(evol)
    s.commit()
print('OK')
" 2>"$MAINT_ERR2" \
    && log "  → nettoyages complétés" \
    || {
        ERREUR_CLEAN=$(cat "$MAINT_ERR2")
        log "  ERREUR nettoyages : $ERREUR_CLEAN"
        GLOBAL_STATUT="erreur"
        GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }nettoyages: $ERREUR_CLEAN"
    }
rm -f "$MAINT_ERR2"

# --- 2b. VACUUM SQLite sur base AU REPOS (API stoppée = 0 writer concurrent) ----
# Une VACUUM réécrit l'intégralité du fichier. La lancer depuis un process tiers
# (`docker exec`) pendant que l'API écrit (la télémétrie insère à chaque page vue)
# corrompt la base — telemetry_event malformée les 05 et 17/06/2026. On stoppe donc
# l'API d'abord, exactement comme bascule.sh phase 3 et la procédure de récupération :
# 0 writer concurrent → VACUUM sûr. On enchaîne un quick_check de contrôle.
log "[2b/5] VACUUM SQLite (API stoppée, base au repos)..."
MAINT_ERR2B=$(mktemp)
DB_DIR=$(docker volume inspect 5hostachy_app_data --format '{{.Mountpoint}}' 2>/dev/null)
if [ -n "$DB_DIR" ] && [ -f "$DB_DIR/app.db" ] && command -v sqlite3 >/dev/null 2>&1; then
    docker stop hostachy_api >/dev/null 2>&1 || true
    if sqlite3 "$DB_DIR/app.db" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM; PRAGMA quick_check;" >"$MAINT_ERR2B" 2>&1 \
       && grep -qx 'ok' "$MAINT_ERR2B"; then
        chown 1000:1000 "$DB_DIR/app.db" 2>/dev/null || true
        log "  → VACUUM OK (quick_check : ok)"
    else
        log "  ERREUR VACUUM : $(cat "$MAINT_ERR2B")"
        GLOBAL_STATUT="erreur"
        GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }VACUUM: $(cat "$MAINT_ERR2B")"
    fi
    docker start hostachy_api >/dev/null 2>&1 \
        || (cd "$REPO" && docker compose up -d api >/dev/null 2>&1) || true
else
    log "  ⚠ VACUUM ignorée (volume/sqlite3 introuvable : DB_DIR='$DB_DIR')"
fi
rm -f "$MAINT_ERR2B"

# --- 2c. Attente readiness API après redémarrage -------------------------------
log "[2c/5] Attente API..."
API_OK=false
for i in $(seq 1 20); do
    if curl -sf http://localhost/api/health >/dev/null 2>&1; then
        API_OK=true
        break
    fi
    sleep 2
done
if $API_OK; then
    log "  → API opérationnelle"
else
    log "  ⚠ API non joignable après 40s — vérifier manuellement"
    GLOBAL_STATUT="erreur"
    GLOBAL_ERREUR="${GLOBAL_ERREUR:+$GLOBAL_ERREUR | }API restart timeout"
fi

# --- 3. Taille DB après VACUUM ---------------------------------------------------
DB_SIZE=$(docker exec hostachy_api python -c \
    "import os; print(os.path.getsize('/app/data/app.db'))" 2>/dev/null) \
    || DB_SIZE="null"

# --- 4. Nettoyage images Docker inutilisées ------------------------------------
log "[4/5] Nettoyage images Docker inutilisées..."
PRUNE_OUT=$(docker image prune -f 2>&1 | tail -1) || PRUNE_OUT="(docker image prune échoué)"
log "  → $PRUNE_OUT"

# --- 4b. Rotation des fichiers de log host ------------------------------------
# Limite chaque fichier de log aux 1000 dernières lignes (≈ 2 ans de crons hebdo).
# Les logs Docker sont déjà bornés par max-file/max-size dans docker-compose.yml.
log "[4b/5] Rotation des logs host..."
for LOGFILE in \
    /var/log/hostachy-maintenance.log \
    /var/log/hostachy-deploy.log \
    /var/log/hostachy-check.log \
    /var/log/hostachy-health-watch.log \
    /var/log/hostachy-bascule.log; do
    if [ -f "$LOGFILE" ]; then
        LINES_BEFORE=$(wc -l < "$LOGFILE")
        tail -1000 "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
        LINES_AFTER=$(wc -l < "$LOGFILE")
        TRIMMED=$(( LINES_BEFORE - LINES_AFTER ))
        if [ "$TRIMMED" -gt 0 ]; then
            log "  → $(basename $LOGFILE) : $TRIMMED ligne(s) supprimée(s), $LINES_AFTER conservée(s)"
        else
            log "  → $(basename $LOGFILE) : OK ($LINES_AFTER lignes)"
        fi
    fi
done

# Le log auto-deploy est écrit par un cron UTILISATEUR (ptressard), pas root : la
# rotation ci-dessus (mv d'un .tmp créé par root) le repasse root-owned → le cron
# user ne peut plus y écrire (Permission denied), et auto-deploy cesse SILENCIEUSEMENT
# de tourner (cause du non-déploiement de rpi1 découvert le 15/07). On restaure
# l'ownership à chaque maintenance = self-healing sur les 2 RPi.
chown 1000:1000 /var/log/hostachy-deploy.log 2>/dev/null || true

# --- 5. Enregistrement dans l'API ------------------------------------------------
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
