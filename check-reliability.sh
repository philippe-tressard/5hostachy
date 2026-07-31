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
HB_MAX_AGE_MIN=20       # battement auto-deploy : 4 ticks de 5 min manqués
CR_MAX_AGE_MIN=40       # exécution de CE script sur le peer : 2 ticks de 15 min manqués
DEPLOY_LOG=/var/log/hostachy-deploy.log
RELIABILITY_LOG=/var/log/hostachy-reliability.log

FAILS=0; WARNS=0; FAIL_LINES=""
ok()   { echo "[ OK ] $*"; }
warn() { echo "[WARN] $*"; WARNS=$((WARNS+1)); }
# Les FAIL sont mémorisés pour l'alerte : celle-ci reprenait les FAIL du LOG
# (`grep '^\[FAIL\]' … | tail -10`), donc l'historique de toutes les exécutions
# passées. Le 30/07/2026 le mail « 1 contrôle en échec » détaillait ainsi SIX
# lignes, dont cinq d'une panne réseau déjà résorbée une heure plus tôt : sujet
# et corps se contredisaient et pointaient une fausse piste. Une alerte décrit
# l'exécution qui la déclenche, rien d'autre.
fail() { echo "[FAIL] $*"; FAIL_LINES+="[FAIL] $*"$'\n'; FAILS=$((FAILS+1)); }

# ── Sonde HTTP — UNE valeur, toujours (cf. health-watch.sh) ──────────────────
http_code() {  # $1 = URL, $2 = timeout (défaut 10) → code HTTP ou 000
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-10}" "$1" 2>/dev/null)
  echo "${code:-000}"
}

# ── Âge du dernier battement horodaté d'un log (minutes) ─────────────────────
# Rend -1 si aucun horodatage exploitable : INCONNU, jamais « récent ».
beat_age_min() {  # $1 = "AAAA-MM-JJ HH:MM:SS" (peut être vide), $2 = epoch de réf.
  local ts="$1" now="${2:-$(date +%s)}" e
  [ -n "$ts" ] || { echo -1; return; }
  e=$(date -d "$ts" +%s 2>/dev/null)
  [ -n "$e" ] || { echo -1; return; }
  echo $(( (now - e) / 60 ))
}

# ── Verdict du battement (PURE — testable) ───────────────────────────────────
# Args : âge en minutes (-1 = inconnu), seuil → "ok" | "absent" | "inconnu"
beat_verdict() {
  local age="$1" max="$2"
  case "$age" in ''|*[!0-9-]*) echo inconnu; return ;; esac
  [ "$age" -lt 0 ] && { echo inconnu; return; }
  [ "$age" -le "$max" ] && echo ok || echo absent
}

# ── Self-test des fonctions pures (aucun effet de bord) ──────────────────────
if [ "${1:-}" = "--selftest" ]; then
  st_fail=0
  check() { # description attendu args…
    local desc="$1" exp="$2"; shift 2
    local got; got=$(beat_verdict "$@")
    if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
    else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
  }
  echo "== self-test check-reliability.beat_verdict =="
  check "battement de 3 min"                    "ok"      3    "$HB_MAX_AGE_MIN"
  check "battement pile au seuil"               "ok"      20   "$HB_MAX_AGE_MIN"
  check "battement de 45 min (script bloqué)"   "absent"  45   "$HB_MAX_AGE_MIN"
  # Le cas qui manquait : l'ancien contrôle comptait `grep -c … || echo 0`, ce qui
  # rendait « 0\n0 » quand il n'y avait AUCUNE ligne. La comparaison d'entiers
  # échouait alors en erreur, l'expression passait à faux… et le contrôle affichait
  # [ OK ] exactement dans le cas qu'il existe pour attraper (log vide/illisible).
  check "aucun horodatage exploitable"          "inconnu" -1   "$HB_MAX_AGE_MIN"
  check "valeur non numérique"                  "inconnu" "0
0"  "$HB_MAX_AGE_MIN"
  echo "-- beat_age_min --"
  AGE=$(beat_age_min "2026-07-30 01:00:00" "$(date -d '2026-07-30 01:30:00' +%s)")
  [ "$AGE" = "30" ] && echo "PASS  âge calculé sur 30 min  → $AGE" || { echo "FAIL  âge attendu=30 obtenu=$AGE"; st_fail=1; }
  AGE=$(beat_age_min "" 0)
  [ "$AGE" = "-1" ] && echo "PASS  horodatage vide → inconnu (-1)" || { echo "FAIL  attendu=-1 obtenu=$AGE"; st_fail=1; }
  AGE=$(beat_age_min "pas une date" 0)
  [ "$AGE" = "-1" ] && echo "PASS  horodatage invalide → inconnu (-1)" || { echo "FAIL  attendu=-1 obtenu=$AGE"; st_fail=1; }
  [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st_fail
fi

# Sourcé APRÈS le bloc --selftest : la CI exécute `bash check-reliability.sh
# --selftest` depuis la racine du dépôt, où $REPO (/opt/5hostachy) n'existe pas.
source "$REPO/lib-role.sh"
SELF=$(role_of "$(hostname)")
[ -n "$SELF" ] || { echo "Hostname inconnu — abandon."; exit 2; }
SELF_IP=$(role_ip "$SELF"); PEER=$(role_peer "$SELF"); PEER_IP=$(role_ip "$PEER")
SSH_CMD="ssh -i /root/.ssh/id_ed25519_bascule -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no"

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
echo "reliability_last=$(tail -3000 /var/log/hostachy-reliability.log 2>/dev/null | grep -oE "check-reliability \([0-9-]{10} [0-9:]{8}\)" | tail -1 | tr -d "()" | cut -d" " -f2-)"
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
CODE=$(http_code "$PUBLIC_URL")
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

# ── C14. Battement d'auto-deploy (les DEUX rôles) ────────────────────────────
# auto-deploy écrit une ligne horodatée à chaque tick (12/h), quel que soit son
# rôle — c'est son contrat de battement. Le 26/07/2026, ces lignes ont disparu
# 7 h 30 : le flag local étant faussement passé à SELF, le garde-fou
# anti-split-brain était franchi et le script mourait plus loin, au `git fetch`,
# en ne laissant que des erreurs git NON HORODATÉES — invisibles à un grep de
# motifs comme à un tri par date. Seule l'absence des lignes attendues le
# révélait.
#
# Le contrôle ne valait d'abord que sur le standby, l'actif n'écrivant RIEN
# quand il n'avait rien à déployer. Deux conséquences, toutes deux vécues :
#   • l'actif n'était PAS couvert — c'est là qu'auto-deploy est resté KO 7
#     semaines (bit x perdu le 21/04, découvert le 07/06) ;
#   • au changement de rôle, l'âge mesuré remontait dans la période ACTIVE, où
#     le silence était normal : la bascule de 02:03 le 31/07/2026 a démoté rpi2,
#     le contrôle de 02:06 a lu le dernier battement de 20:03 (nœud actif et
#     muet depuis) et a envoyé un mail d'échec pour une infra saine — le premier
#     tick de standby, à 02:08, remettait tout au vert. La fenêtre était
#     structurelle : elle se rouvrait à chaque bascule nocturne.
# auto-deploy émet désormais aussi son battement sur l'actif ; l'âge du dernier
# tick est comparable dans les deux rôles et ce contrôle vaut partout.
#
# Mesuré par l'ÂGE du dernier battement horodaté, et non plus par un comptage
# de lignes par tranche horaire (correctif du 30/07/2026). L'ancienne version
# avait deux défauts, tous deux constatés cette nuit-là :
#   • `grep -c … || echo 0` rendait « 0\n0 » quand le log ne contenait AUCUNE
#     ligne — la comparaison d'entiers échouait en erreur et le contrôle
#     affichait [ OK ] précisément dans le cas qu'il devait attraper ;
#   • les tranches horaires traînent : à 02:06, alors que tout était vert
#     depuis 01:46, le contrôle échouait encore sur les compteurs de 01:00-01:59
#     et a déclenché un mail décrivant une panne terminée. L'âge, lui, se
#     résorbe de lui-même dès le premier tick revenu.
ROLE=$([ "${S_active:-}" = "$SELF" ] && echo actif || echo standby)
HB_LAST=$(grep -oE '^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\]' "$DEPLOY_LOG" 2>/dev/null | tail -1 | tr -d '[]')
HB_AGE=$(beat_age_min "$HB_LAST")
case "$(beat_verdict "$HB_AGE" "$HB_MAX_AGE_MIN")" in
  ok)      ok "Battement auto-deploy présent sur $SELF ($ROLE) : dernier tick il y a ${HB_AGE} min" ;;
  absent)  fail "Battement auto-deploy absent sur $SELF ($ROLE) : dernier tick il y a ${HB_AGE} min (attendu ≤ ${HB_MAX_AGE_MIN}) → le script ne va plus au bout" ;;
  *)       fail "Battement auto-deploy INCONNU sur $SELF ($ROLE) : aucun horodatage exploitable dans $DEPLOY_LOG (log vide, illisible ou format changé)" ;;
esac

# ── C15. Le contrôleur lui-même tourne-t-il sur le PEER ? ────────────────────
# Rien ne surveillait check-reliability : s'il cesse de tourner (cron perdu, bit
# x envolé, nœud figé), il ne peut par construction pas le signaler — son
# silence est indiscernable du vert. Même angle mort que le battement
# auto-deploy muet sur l'actif (C14), et même mesure : l'âge du dernier
# horodatage. Chaque nœud contrôle donc l'AUTRE — s'auto-contrôler ne prouverait
# rien, puisque le cas à attraper est précisément « ce script ne s'exécute pas ».
if [ "$PEER_OK" -eq 0 ]; then
  CR_AGE=$(beat_age_min "${P_reliability_last:-}")
  case "$(beat_verdict "$CR_AGE" "$CR_MAX_AGE_MIN")" in
    ok)      ok "check-reliability tourne sur $PEER : dernière exécution il y a ${CR_AGE} min" ;;
    absent)  fail "check-reliability ne tourne plus sur $PEER : dernière exécution il y a ${CR_AGE} min (attendu ≤ ${CR_MAX_AGE_MIN}) → cron perdu, bit x, ou nœud figé" ;;
    *)       fail "check-reliability INCONNU sur $PEER : aucune exécution horodatée dans $RELIABILITY_LOG (log vide, illisible ou format changé)" ;;
  esac
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
      "$(printf 'check-reliability.sh sur %s a relevé %s FAIL et %s WARN à %s.\n\nDétail (cette exécution) :\n%s\nLog complet : /var/log/hostachy-reliability.log\n' \
          "$SELF" "$FAILS" "$WARNS" "$(date '+%d/%m/%Y %H:%M')" "$FAIL_LINES")"
  else
    echo "[WARN] lib-alert.sh introuvable dans $REPO — aucune alerte envoyée."
  fi
fi

exit "$FAILS"
