#!/bin/bash
# =============================================================================
#  check-reliability.sh — Contrôles de fiabilité de l'infra HA 5Hostachy
#
#  Audite les invariants des DEUX RPi et signale toute dérive AVANT qu'elle ne
#  provoque un incident (split-brain, dubious-ownership root, logs non rotés…).
#
#  Conçu pour tourner en root (utilise la clé SSH de bascule pour joindre le peer),
#  comme les autres contrôles cron. Sortie : [ OK ] / [WARN] / [FAIL] par contrôle.
#  Code de sortie = nombre de FAIL (0 = tout vert) → exploitable par cron (MAILTO).
#
#  Cron suggéré (sudo crontab, sur les 2 RPi) :
#    */15 * * * * /opt/5hostachy/check-reliability.sh >> /var/log/hostachy-reliability.log 2>&1
#
#  Lancement manuel : sudo /opt/5hostachy/check-reliability.sh
# =============================================================================
set -uo pipefail

REPO=/opt/5hostachy
PUBLIC_URL="https://5hostachy.fr/api/health"
DISK_WARN=85; DISK_FAIL=95
LOG_WARN_MB=5
SKEW_WARN_S=5
LOCK_STALE_MIN=20

case "$(hostname)" in
  PhT-RB5)   SELF="rpi1"; SELF_IP="192.168.1.222"; PEER_IP="192.168.1.223"; PEER="rpi2" ;;
  PhT-RB5i2) SELF="rpi2"; SELF_IP="192.168.1.223"; PEER_IP="192.168.1.222"; PEER="rpi1" ;;
  *) echo "Hostname inconnu — abandon."; exit 2 ;;
esac
SSH_CMD="ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no"

FAILS=0; WARNS=0
ok()   { echo "[ OK ] $*"; }
warn() { echo "[WARN] $*"; WARNS=$((WARNS+1)); }
fail() { echo "[FAIL] $*"; FAILS=$((FAILS+1)); }

# ── Snippet de collecte exécuté sur chaque nœud (local + peer) ───────────────
# Émet des lignes key=value. Tout est tolérant aux erreurs (jamais d'exit ≠ 0).
COLLECT='
R=/opt/5hostachy
echo "host=$(hostname)"
echo "active=$(cat $R/.active 2>/dev/null | tr -d "[:space:]")"
echo "containers=$(docker ps -q --filter name=hostachy 2>/dev/null | wc -l | tr -d " ")"
echo "cf_active=$(systemctl is-active cloudflared 2>/dev/null)"
echo "cf_enabled=$(systemctl is-enabled cloudflared 2>/dev/null)"
echo "head=$(git -C $R rev-parse --short HEAD 2>/dev/null)"
echo "origin_head=$(git -C $R rev-parse --short origin/main 2>/dev/null)"
echo "git_root_ok=$(git -C $R rev-parse HEAD >/dev/null 2>&1 && echo yes || echo no)"
BITS=ok; for s in bascule.sh health-watch.sh maintenance.sh auto-deploy.sh MaJ-Hostachy.sh check-reliability.sh boot-role-guard.sh; do [ -f "$R/$s" ] && [ ! -x "$R/$s" ] && BITS="manque:$s"; done
echo "exec_bits=$BITS"
echo "disk=$(df / | awk "NR==2{print \$5}" | tr -d %)"
echo "ntp=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)"
echo "epoch=$(date +%s)"
echo "lock=$([ -f $R/.bascule-lock ] && stat -c %Y $R/.bascule-lock || echo 0)"
BIG=""; for l in /var/log/hostachy-*.log; do [ -f "$l" ] || continue; sz=$(( $(stat -c %s "$l")/1048576 )); [ "$sz" -ge '"$LOG_WARN_MB"' ] && BIG="$BIG $(basename $l):${sz}M"; done
echo "biglogs=$BIG"
echo "deploylog_owner=$(stat -c %U /var/log/hostachy-deploy.log 2>/dev/null || echo missing)"
'

# ⚠ PAS de contrôle d'intégrité DB ici — SUPPRIMÉ le 17/07/2026 (cf. C8 plus bas).
# Ce script ne doit JAMAIS ouvrir app.db : il tourne toutes les 15 min et l'ouverture
# de la base depuis un process tiers casse le WAL de l'API live (détail au contrôle C8).
# L'intégrité est vérifiée in-process par l'API : backup.py (03:00) + health_monitor.py (06:00).

parse() { # $1=prefix $2=raw → définit ${PREFIX}_key
  local p=$1; while IFS='=' read -r k v; do [ -n "$k" ] && eval "${p}_${k}=\"\$v\""; done <<< "$2"
}

echo "═══════════ check-reliability ($(date '+%Y-%m-%d %H:%M:%S')) — vu depuis $SELF ═══════════"

S_RAW=$(bash -c "$COLLECT" 2>/dev/null); parse S "$S_RAW"
P_RAW=$($SSH_CMD ptressard@"$PEER_IP" "$COLLECT" 2>/dev/null); PEER_OK=$?
if [ $PEER_OK -ne 0 ] || [ -z "$P_RAW" ]; then
  fail "Peer $PEER ($PEER_IP) injoignable en SSH — impossible d'auditer les 2 nœuds."
  P_containers=0; P_cf_active=unknown; P_active=unknown; P_head=unknown
  P_git_root_ok=unknown; P_exec_bits=unknown; P_epoch=0; P_cf_enabled=unknown
else
  parse P "$P_RAW"
fi

# Identifier qui PORTE réellement la prod (vérité terrain = conteneurs qui tournent)
RUNNING=""
[ "${S_containers:-0}" -gt 0 ] && RUNNING="$RUNNING $SELF"
[ "${P_containers:-0}" -gt 0 ] && RUNNING="$RUNNING $PEER"
RUNNING=$(echo "$RUNNING" | xargs)

# ── C1. Public joignable ─────────────────────────────────────────────────────
CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$PUBLIC_URL" 2>/dev/null || echo 000)
[ "$CODE" = "200" ] && ok "Site public répond (HTTP 200)" || fail "Site public KO (HTTP $CODE)"

# ── C2. Split-brain : un seul nœud porte les conteneurs ──────────────────────
case "$(echo "$RUNNING" | wc -w)" in
  1) ok "Pas de split-brain — conteneurs uniquement sur $RUNNING" ;;
  0) fail "Aucun nœud ne fait tourner de conteneurs (site HS ?)" ;;
  *) fail "SPLIT-BRAIN — conteneurs actifs sur les 2 nœuds ($RUNNING)" ;;
esac

# ── C3. cloudflared : exactement un actif, cohérent avec le rôle ─────────────
CF_ON=""; [ "${S_cf_active:-}" = "active" ] && CF_ON="$CF_ON $SELF"; [ "${P_cf_active:-}" = "active" ] && CF_ON="$CF_ON $PEER"; CF_ON=$(echo "$CF_ON" | xargs)
case "$(echo "$CF_ON" | wc -w)" in
  1) ok "cloudflared actif sur un seul nœud ($CF_ON)" ;;
  *) fail "cloudflared incohérent — actif sur: '${CF_ON:-aucun}' (doit être exactement 1)" ;;
esac
# actif=enabled (survit reboot), standby=disabled (pas d'auto-start → pas de split-brain au boot)
if [ "${S_active:-}" = "$SELF" ]; then ACT_ENABLED=${S_cf_enabled:-?}; STBY_ENABLED=${P_cf_enabled:-?}; ACTN=$SELF; STBN=$PEER
else ACT_ENABLED=${P_cf_enabled:-?}; STBY_ENABLED=${S_cf_enabled:-?}; ACTN=$PEER; STBN=$SELF; fi
[ "$ACT_ENABLED" = "enabled" ] || warn "cloudflared sur l'actif ($ACTN) est '$ACT_ENABLED' (attendu enabled → survit à un reboot)"
[ "$STBY_ENABLED" = "disabled" ] || warn "cloudflared sur le standby ($STBN) est '$STBY_ENABLED' (attendu disabled → pas d'auto-start = pas de split-brain au reboot)"

# ── C4. .active cohérent entre les 2 et conforme à la réalité terrain ────────
if [ "${S_active:-}" = "${P_active:-}" ] && [ -n "${S_active:-}" ]; then
  ok ".active cohérent sur les 2 nœuds (= ${S_active})"
  [ "$(echo "$RUNNING" | wc -w)" = "1" ] && [ "$RUNNING" != "${S_active}" ] && fail ".active=${S_active} mais les conteneurs tournent sur $RUNNING (flag erroné)"
else
  fail ".active divergent — $SELF='${S_active:-?}' vs $PEER='${P_active:-?}'"
fi

# ── C5. CONTRÔLE ROOT : git exécutable par root (dubious-ownership) ──────────
# Cause racine de la bascule HS du 17/06 : repo possédé par ptressard, cron root →
# "dubious ownership". Ce contrôle l'attrape avant la prochaine bascule.
[ "${S_git_root_ok:-no}" = "yes" ] && ok "git utilisable par root sur $SELF" || fail "git CASSÉ pour root sur $SELF (dubious-ownership ? → 'git config --system --add safe.directory $REPO')"
if [ "$PEER_OK" -eq 0 ]; then
  [ "${P_git_root_ok:-no}" = "yes" ] && ok "git utilisable par root sur $PEER" || fail "git CASSÉ pour root sur $PEER (→ safe.directory $REPO en root)"
fi

# ── C6. Bits d'exécution des scripts cron ────────────────────────────────────
[ "${S_exec_bits:-}" = "ok" ] && ok "Bits exec scripts OK sur $SELF" || fail "Bit exec manquant sur $SELF (${S_exec_bits:-?})"
[ "$PEER_OK" -eq 0 ] && { [ "${P_exec_bits:-}" = "ok" ] && ok "Bits exec scripts OK sur $PEER" || fail "Bit exec manquant sur $PEER (${P_exec_bits:-?})"; }

# ── C7. Parité de code : actif aligné sur origin/main ────────────────────────
if [ "$ACTN" = "$SELF" ]; then AH=${S_head:-?}; AOH=${S_origin_head:-?}; else AH=${P_head:-?}; AOH=${P_origin_head:-?}; fi
[ "$AH" = "$AOH" ] && ok "Code actif ($ACTN) aligné sur origin/main ($AH)" || warn "Actif ($ACTN) à $AH, origin/main à $AOH — déploiement en retard ?"

# ── C8. SUPPRIMÉ le 17/07/2026 — ce contrôle CAUSAIT des pertes de données ───
# Il faisait `docker exec hostachy_api python3` + PRAGMA quick_check toutes les 15 min.
# Bien que read-only, ouvrir une base WAL depuis un PROCESS TIERS et la refermer est
# destructeur : les connexions du pool SQLAlchemy de l'API sont ouvertes mais SANS VERROU
# quand elles sont idle → SQLite croit être la dernière connexion → checkpoint + unlink de
# `app.db-wal`/`app.db-shm`. L'API continue alors d'écrire dans des inodes ORPHELINS :
# writes invisibles aux autres connexions, `disk I/O error` (SQLITE_IOERR), et surtout
# PERTE des données au prochain arrêt (le checkpoint de shutdown échoue → WAL abandonné).
# Incident 17/07/2026 : login en 503 + ~12 h d'écritures perdues (2 publications, 1 modif,
# 1 suppression annulée). Cf. règle d'or CLAUDE.md + commentaire admin.py `/db/checkpoint`.
#
# NE PAS réintroduire : l'intégrité est DÉJÀ vérifiée in-process, sans process tiers, par
#   • backup.py            → quick_check avant chaque sauvegarde (03:00), backup annulé si KO
#   • health_monitor.py    → _check_db_integrity() (06:00) + alerte email
# Un contrôle à chaud ici n'apporterait rien et ne peut PAS se faire via docker exec.
# Si un jour une granularité 15 min est vraiment requise : endpoint in-process
# `GET /admin/db/integrite` (require_admin → nécessite un moyen d'auth pour le cron root),
# ou un job APScheduler qui écrit un fichier de statut que ce script se contente de LIRE.

# ── C9. Disque ───────────────────────────────────────────────────────────────
for pair in "$SELF:${S_disk:-0}" "$PEER:${P_disk:-0}"; do
  n=${pair%:*}; d=${pair#*:}; [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
  if [ "${d:-0}" -ge "$DISK_FAIL" ]; then fail "Disque $n à ${d}% (critique)"
  elif [ "${d:-0}" -ge "$DISK_WARN" ]; then warn "Disque $n à ${d}%"
  else ok "Disque $n à ${d}%"; fi
done

# ── C10. Logs non rotés (croissance infinie) ─────────────────────────────────
[ -n "${S_biglogs:-}" ] && warn "Logs volumineux sur $SELF :${S_biglogs}" || ok "Tailles de logs OK sur $SELF"
[ "$PEER_OK" -eq 0 ] && { [ -n "${P_biglogs:-}" ] && warn "Logs volumineux sur $PEER :${P_biglogs}" || ok "Tailles de logs OK sur $PEER"; }

# ── C11. NTP + dérive d'horloge entre les 2 (cron/bascule en dépendent) ──────
[ "${S_ntp:-}" = "yes" ] && ok "NTP synchronisé sur $SELF" || warn "NTP non synchronisé sur $SELF"
if [ "$PEER_OK" -eq 0 ]; then
  [ "${P_ntp:-}" = "yes" ] && ok "NTP synchronisé sur $PEER" || warn "NTP non synchronisé sur $PEER"
  SKEW=$(( ${S_epoch:-0} - ${P_epoch:-0} )); SKEW=${SKEW#-}
  [ "$SKEW" -le "$SKEW_WARN_S" ] && ok "Dérive d'horloge entre les 2 = ${SKEW}s" || warn "Dérive d'horloge ${SKEW}s entre $SELF et $PEER (> ${SKEW_WARN_S}s)"
fi

# ── C12. Lock de bascule orphelin ────────────────────────────────────────────
NOW=$(date +%s)
for pair in "$SELF:${S_lock:-0}" "$PEER:${P_lock:-0}"; do
  n=${pair%:*}; t=${pair#*:}; [ "${t:-0}" -eq 0 ] && continue
  age=$(( (NOW - t) / 60 ))
  [ "$age" -ge "$LOCK_STALE_MIN" ] && warn ".bascule-lock orphelin sur $n (âge ${age} min — bascule/MAJ figée ?)" || ok ".bascule-lock récent sur $n (${age} min — opération en cours)"
done

# ── C13. Log auto-deploy inscriptible par le cron USER (sinon auto-deploy KO) ─
# auto-deploy = SEUL cron user ; /var/log est root:root. Si le log repasse
# root-owned (rotation maintenance en root), la redirection du cron user échoue
# → auto-deploy ne tourne plus SILENCIEUSEMENT (bug rpi1 du 15/07). maintenance.sh
# re-chown le log après rotation ; ce contrôle attrape toute régression.
for pair in "$SELF:${S_deploylog_owner:-missing}" "$PEER:${P_deploylog_owner:-missing}"; do
  n=${pair%:*}; o=${pair#*:}; [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
  [ "$o" = "ptressard" ] && ok "Log auto-deploy inscriptible par le cron user sur $n" \
    || warn "Log auto-deploy NON inscriptible par le cron user sur $n (owner=$o) → auto-deploy silencieusement KO (sudo chown ptressard:ptressard /var/log/hostachy-deploy.log)"
done

# ── C14. Battement d'auto-deploy sur le STANDBY ──────────────────────────────
# Sur le standby, auto-deploy écrit une ligne « n'est pas l'actif — ignoré » à
# chaque tick (12/h). Sur l'ACTIF il n'écrit RIEN quand il n'y a pas de
# changement : le silence y est normal, ce contrôle ne vaut donc que sur le
# standby. Le 26/07/2026, ces lignes ont disparu 7 h 30 : le flag local étant
# faussement passé à SELF, le garde-fou anti-split-brain était franchi et le
# script mourait plus loin, au `git fetch`, en ne laissant que des erreurs git
# NON HORODATÉES — invisibles à un grep de motifs comme à un tri par date. Seule
# l'absence des lignes attendues le révélait.
if [ "${S_active:-}" != "$SELF" ]; then
  HB=$(grep -c "$(date '+%Y-%m-%d %H')" /var/log/hostachy-deploy.log 2>/dev/null || echo 0)
  HB_PREV=$(grep -c "$(date -d '1 hour ago' '+%Y-%m-%d %H')" /var/log/hostachy-deploy.log 2>/dev/null || echo 0)
  # Sur l'heure écoulée on attend ~12 lignes ; on alerte bien en dessous pour
  # tolérer une rotation de log ou un décalage de tick.
  if [ "${HB_PREV:-0}" -lt 6 ] && [ "${HB:-0}" -lt 6 ]; then
    fail "Battement auto-deploy absent sur $SELF (standby) : ${HB} ligne(s) cette heure, ${HB_PREV} la précédente (attendu ~12) → le script ne va plus au bout"
  else
    ok "Battement auto-deploy présent sur $SELF (standby) : ${HB} cette heure, ${HB_PREV} la précédente"
  fi
fi

echo "─────────────────────────────────────────────────────────────"
echo "Résumé : $FAILS FAIL, $WARNS WARN"
[ "$FAILS" -eq 0 ] && echo "✅ Tous les contrôles critiques sont verts." || echo "❌ $FAILS contrôle(s) critique(s) en échec — intervention requise."

# ── Alerte e-mail sur échec critique ─────────────────────────────────────────
# Sans ceci, un FAIL n'allait QUE dans /var/log/hostachy-reliability.log (le cron
# redirige tout, donc MAILTO ne reçoit rien) : le 26/07/2026 le C4 a signalé
# « .active divergent » neuf fois de suite, failover neutralisé et site HS ~50 min,
# sans que personne ne soit prévenu. La détection marchait — pas la notification.
if [ "$FAILS" -gt 0 ]; then
  # shellcheck source=/dev/null
  if [ -r "$REPO/lib-alert.sh" ]; then
    ALERT_COOLDOWN_FILE=/tmp/check-reliability-cooldown
    ALERT_COOLDOWN_SECONDS=3600   # 1 h : à */15 un FAIL persistant ferait 96 mails/jour
    ALERT_REPO="$REPO"
    source "$REPO/lib-alert.sh"
    alert_if_not_in_cooldown \
      "[5Hostachy] ❌ $FAILS contrôle(s) de fiabilité en échec sur $SELF" \
      "$(printf 'check-reliability.sh sur %s a relevé %s FAIL et %s WARN.\n\nDétail :\n%s\n\nLog complet : /var/log/hostachy-reliability.log\n' \
          "$SELF" "$FAILS" "$WARNS" "$(grep -E '^\[FAIL\]' /var/log/hostachy-reliability.log 2>/dev/null | tail -10)")"
  else
    echo "[WARN] lib-alert.sh introuvable dans $REPO — aucune alerte envoyée."
  fi
fi

exit "$FAILS"
