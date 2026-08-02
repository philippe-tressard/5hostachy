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

# Rotation : nombre de lignes conservées par fichier de log host.
# 1000 lignes convenaient à un cron hebdomadaire ; les logs à haute fréquence
# écrivent 100× plus (reliability : 22 lignes × 96 exécutions = ~2 100/jour).
# 20 000 lignes = ~9 jours pour le plus bavard, plusieurs années pour le moins
# bavard, et ~1 Mo par fichier — sous le seuil d'alerte C10 (5 Mo).
LOG_KEEP_LINES=20000
# Cache de build BuildKit : plafond conservé (les couches les plus récemment
# utilisées sont gardées en priorité). Ne pas descendre trop bas : la bascule
# nocturne rebuilde l'image du peer à chaque fois et compte sur ce cache pour
# ne PAS rejouer `npm run build` (risque d'OOM sur RPi).
BUILD_CACHE_KEEP=10737418240   # 10 Go
BUILD_CACHE_MAX_AGE_H=168      # 7 j : au-delà, une couche est périmée pour tous
# Projet Compose de cette application. Sert à ne purger QUE ses propres images
# sur un daemon partagé (rpi2 co-héberge List-dons, projet `listdons`).
COMPOSE_PROJECT=5hostachy

# --- Hygiène locale : à faire sur les DEUX nœuds ------------------------------
# Rotation des logs, ownership du log auto-deploy, purge des images et du cache
# de build. Aucune de ces tâches ne touche l'application ni la base — les
# conditionner au rôle n'avait aucune justification technique et laissait le
# standby dériver, puisqu'un nœud n'est actif qu'un dimanche sur deux (bascule
# nocturne alternée). Constaté le 31/07/2026 : 80 218 lignes dans
# hostachy-check.log et ~60 Go de cache de build sur le nœud standby.
# Chiffres produits par hygiene_locale(), pour le rapport envoyé à l'API.
# Ils étaient jusqu'ici écrits dans le log local et perdus : le 02/08/2026, le
# standby avait purgé 3,358 Go de cache et roté 66 338 lignes sans qu'aucune
# trace n'apparaisse dans l'application.
HYG_IMAGES=""; HYG_CACHE_AGE=""; HYG_CACHE_PLAFOND=""; HYG_LIGNES_ROTEES=0

hygiene_locale() {
    # Images sans tag (couches orphelines des rebuilds), **du projet 5hostachy
    # seulement**. Le daemon Docker de rpi2 est partagé avec List-dons, co-hébergé :
    # un `docker image prune` nu supprimerait aussi SES couches orphelines. Arbitrer
    # sur les ressources d'une autre application n'est pas le rôle de cette
    # maintenance — l'isolation vaut dans les deux sens. Les images construites par
    # compose portent `com.docker.compose.project`, ce qui rend le filtre exact.
    # Aucune image référencée par un conteneur, même arrêté (standby), n'est touchée.
    log "[Hygiène] Nettoyage des images sans tag du projet $COMPOSE_PROJECT..."
    PRUNE_OUT=$(docker image prune -f --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" 2>&1 | tail -1) \
        || PRUNE_OUT="(échec du prune d'images)"
    log "  → $PRUNE_OUT"
    HYG_IMAGES="$PRUNE_OUT"

    # Cache de build : JAMAIS purgé jusqu'au 31/07/2026 — `docker image prune`
    # ne le touche pas. Depuis que la bascule rebuilde systématiquement l'image
    # du peer (v2.20.19), il grossit toutes les nuits sur les deux nœuds :
    # 1113 entrées / ~64 Go sur rpi1 (disque à 66 %) et ~59 Go sur rpi2.
    #
    # ⚠ C'est le SEUL point de ce ménage qui ne peut pas être cloisonné :
    # `docker builder prune` n'accepte aucun filtre par projet (Docker 29 :
    # until / id / parents / description / inuse / private / shared / type), et le
    # cache BuildKit est commun à tout le daemon. Un builder dédié
    # (`docker buildx create`) le cloisonnerait vraiment, mais imposerait un
    # `--builder` à tous les builds (auto-deploy ET bascule phase 0) et un driver
    # conteneur sur un RPi : trop risqué pour l'enjeu.
    # Donc : purge par ÂGE d'abord — une couche inutilisée depuis plus de 7 jours
    # est périmée pour tout le monde, et les couches fraîches de List-dons y
    # survivent — puis plafond de taille en simple garde-fou.
    log "[Hygiène] Purge du cache de build inutilisé depuis > ${BUILD_CACHE_MAX_AGE_H} h..."
    BPRUNE_AGE=$(docker builder prune -f --filter "until=${BUILD_CACHE_MAX_AGE_H}h" 2>&1 | tail -1) \
        || BPRUNE_AGE="(purge par âge échouée)"
    log "  → $BPRUNE_AGE"
    HYG_CACHE_AGE="$BPRUNE_AGE"
    log "[Hygiène] Garde-fou : plafond $(( BUILD_CACHE_KEEP / 1073741824 )) Go..."
    BPRUNE_OUT=$(docker builder prune -f --max-used-space "$BUILD_CACHE_KEEP" 2>&1 | tail -1) \
        || BPRUNE_OUT="(plafonnement échoué)"
    log "  → $BPRUNE_OUT"
    HYG_CACHE_PLAFOND="$BPRUNE_OUT"

    # Rotation par GLOB, et non par liste nominative : hostachy-reliability.log
    # (1,7 Mo, 33 500 lignes) et hostachy-role-guard.log avaient été ajoutés au
    # système sans l'être ici, et n'ont donc jamais été rotés. Le glob couvre
    # d'office tout log ajouté plus tard.
    log "[Hygiène] Rotation des logs host (${LOG_KEEP_LINES} lignes max)..."
    for LOGFILE in /var/log/hostachy-*.log; do
        [ -f "$LOGFILE" ] || continue
        LINES_BEFORE=$(wc -l < "$LOGFILE")
        tail -"$LOG_KEEP_LINES" "$LOGFILE" > "${LOGFILE}.tmp" && mv "${LOGFILE}.tmp" "$LOGFILE"
        LINES_AFTER=$(wc -l < "$LOGFILE")
        TRIMMED=$(( LINES_BEFORE - LINES_AFTER ))
        if [ "$TRIMMED" -gt 0 ]; then
            log "  → $(basename "$LOGFILE") : $TRIMMED ligne(s) supprimée(s), $LINES_AFTER conservée(s)"
            HYG_LIGNES_ROTEES=$(( HYG_LIGNES_ROTEES + TRIMMED ))
        else
            log "  → $(basename "$LOGFILE") : OK ($LINES_AFTER lignes)"
        fi
    done

    # Le log auto-deploy est écrit par un cron UTILISATEUR (ptressard), pas root : la
    # rotation ci-dessus (mv d'un .tmp créé par root) le repasse root-owned → le cron
    # user ne peut plus y écrire (Permission denied), et auto-deploy cesse SILENCIEUSEMENT
    # de tourner (cause du non-déploiement de rpi1 découvert le 15/07). On restaure
    # l'ownership à chaque maintenance = self-healing sur les 2 RPi.
    chown 1000:1000 /var/log/hostachy-deploy.log 2>/dev/null || true
}

# ── Envoi du rapport à l'API — UNE seule implémentation ───────────────────────
#  $1 = portée : "applicative" (nœud actif) | "hygiene_locale" (standby)
#
#  POURQUOI le standby doit poster ailleurs que sur localhost :
#  il n'y a pas d'API sur le nœud passif (les conteneurs ne tournent que sur
#  l'actif). Le POST vers http://localhost échouait donc silencieusement, et
#  tout le ménage du standby restait invisible dans l'application — constaté le
#  02/08/2026. Il poste désormais vers l'IP de l'ACTIF, résolue par lib-role.sh
#  (aucune table d'adresses recopiée ici).
#
#  Cette fonction ne fait JAMAIS échouer la maintenance : le ménage a déjà eu
#  lieu quand elle s'exécute, et perdre le rapport ne doit pas transformer un
#  succès en échec.
envoyer_rapport() {
    local portee="$1" cible="http://localhost" ip=""

    MAINTENANCE_KEY=$(grep -E '^MAINTENANCE_KEY=' "$REPO/.env" 2>/dev/null \
        | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'") || MAINTENANCE_KEY=""
    if [ -z "$MAINTENANCE_KEY" ]; then
        log "  ⚠ MAINTENANCE_KEY absent du .env — rapport non enregistré"
        return 0
    fi

    if [ "$portee" = "hygiene_locale" ]; then
        [ -n "${ACTIVE:-}" ] || { log "  ⚠ Nœud actif inconnu — rapport non enregistré"; return 0; }
        command -v role_ip >/dev/null 2>&1 || source "$REPO/lib-role.sh" 2>/dev/null || true
        ip=$(role_ip "$ACTIVE" 2>/dev/null) || ip=""
        if [ -z "$ip" ]; then
            log "  ⚠ IP de l'actif ($ACTIVE) introuvable — rapport non enregistré"
            return 0
        fi
        cible="http://$ip"
    fi

    local details erreur_json duree fin
    fin=$(date -u +%Y-%m-%dT%H:%M:%S)
    duree=$(( SECONDS - MAINTE_START ))
    erreur_json=$(echo "${GLOBAL_ERREUR:-}" | sed 's/"/\\"/g')
    details=$(printf \
        '{"images":"%s","cache_age":"%s","cache_plafond":"%s","lignes_rotees":%d,"tokens":%s,"prt":%s,"notifications":%s,"historique":%s,"emails":%s}' \
        "${HYG_IMAGES//\"/}" "${HYG_CACHE_AGE//\"/}" "${HYG_CACHE_PLAFOND//\"/}" \
        "${HYG_LIGNES_ROTEES:-0}" "${DELETED:-0}" "${DELETED_PRT:-0}" \
        "${DELETED_NOTIF:-0}" "${DELETED_HIST:-0}" "${DELETED_EMAILS:-0}")

    local payload http
    payload=$(printf \
        '{"tache":"maintenance","noeud":"%s","portee":"%s","statut":"%s","tokens_supprimes":%s,"taille_db_octets":%s,"duree_secondes":%d,"details":%s,"erreur":"%s","cree_le":"%s","terminee_le":"%s"}' \
        "${SELF:-}" "$portee" "$GLOBAL_STATUT" "${DELETED:-0}" "${DB_SIZE:-null}" \
        "$duree" "$details" "$erreur_json" "$MAINTE_DEBUT" "$fin")

    http=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 \
        -X POST "$cible/api/admin/maintenance/rapport" \
        -H "Content-Type: application/json" \
        -H "x-maintenance-key: $MAINTENANCE_KEY" \
        -d "$payload" 2>/dev/null) || http="000"
    if [ "$http" = "201" ]; then
        log "  → Rapport $portee enregistré sur $cible (HTTP $http)"
    else
        log "  ⚠ Rapport $portee non enregistré sur $cible (HTTP $http)"
    fi
    return 0
}

log ""
log "===== Maintenance Hostachy ====="

# --- Vérification : ce RPi est-il le RPi actif ? ------------------------------
# Seule la partie APPLICATIVE (base, API, rapport) exige d'être l'actif.
FLAG="$REPO/.active"
if [ -f "$FLAG" ]; then
    source "$REPO/lib-role.sh"
    SELF=$(role_of "$(hostname)")
    ACTIVE=$(cat "$FLAG" | tr -d '[:space:]')
    if [ -n "$SELF" ] && [ "$ACTIVE" != "$SELF" ]; then
        log "Ce RPi ($SELF) n'est pas actif ($ACTIVE) — maintenance applicative ignorée."
        hygiene_locale
        # Le ménage du standby est réel (cache de build, rotation des logs) :
        # il doit laisser une trace consultable, sur l'API de l'ACTIF.
        envoyer_rapport "hygiene_locale"
        log "===== Hygiène locale terminée (standby) ====="
        exit 0
    fi
fi

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

# --- 4. Hygiène locale (images, cache de build, rotation des logs) --------------
# Même traitement que sur le standby — une seule implémentation, cf. hygiene_locale().
hygiene_locale

# --- 5. Enregistrement dans l'API ------------------------------------------------
# Même fonction que sur le standby : la logique d'envoi (clé, cible, payload,
# code de retour) n'existe qu'à un seul endroit — cf. envoyer_rapport().
DUREE=$(( SECONDS - MAINTE_START ))
envoyer_rapport "applicative"

log "===== Maintenance terminée (${DUREE}s, statut: $GLOBAL_STATUT) ====="
