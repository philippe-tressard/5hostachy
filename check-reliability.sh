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
MAINT_MAX_AGE_MIN=11520 # maintenance hebdomadaire : 8 j, un dimanche manqué toléré

# ── Cache de build : le seuil se DÉDUIT de la politique de rétention ──────────
# Le seuil valait 20 Go, « déduit » du plafond de 10 Go appliqué le dimanche :
# le double, donc la purge est en panne. C'était faux, et le contrôle criait au
# loup 4 jours sur 7 sur une infra saine (constaté le 06/08/2026, WARN sur les
# 2 nœuds alors que la purge du 02/08 avait bien réclamé 1,76 Go sur rpi1 et
# 3,36 Go sur rpi2). Le plafond n'est pas un régime : il est appliqué UNE fois
# par semaine, et le cache regrossit ensuite d'environ 3,1 Go par nuit — la
# bascule reconstruit l'image du peer chaque nuit depuis la v2.20.19. Le régime
# stationnaire de la rétention à 7 jours est donc le plafond PLUS six nuits, soit
# ~29 Go la veille du dimanche suivant : au-dessus du seuil qui le surveillait.
#
# Le seuil doit donc dépasser ce régime, sinon il ne mesure pas ce qu'il croit.
# Les trois valeurs sont explicites pour que la relation soit vérifiable — le
# self-test échoue si le seuil redescend sous le régime, ce qui interdit de le
# re-déduire du seul plafond comme la première fois.
BUILD_CACHE_FLOOR_GB=10   # plafond appliqué chaque dimanche par maintenance.sh
BUILD_CACHE_GROWTH_GB=4   # croissance par nuit (3,1 Go mesurés, arrondi prudent)
BUILD_CACHE_WARN_GB=40    # > 10 + 6 nuits × 4 = 34 Go de régime, avec marge

DEPLOY_LOG=/var/log/hostachy-deploy.log
RELIABILITY_LOG=/var/log/hostachy-reliability.log
MAINT_LOG=/var/log/hostachy-maintenance.log

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

# ── Empreinte des scripts planifiés dans un crontab (PURE — testable) ────────
# Rend la liste TRIÉE et dédoublonnée des scripts `/opt/5hostachy/*.sh` invoqués,
# séparés par des virgules — ou une chaîne vide si le crontab est illisible.
#
# On compare volontairement le SEUL ensemble de scripts, pas les horaires : deux
# nœuds peuvent écrire `*/5` et `2,7,12,…` pour la même cadence, et un contrôle
# qui hurlerait là-dessus serait exactement le faux positif qu'on vient de retirer
# de C16. La borne est donc assumée (§12 du socle) : ce contrôle attrape « un
# script planifié d'un seul côté », pas « planifié à un rythme différent ».
crontab_scripts() {  # $1 = texte brut du crontab → "a.sh,b.sh" | ""
  echo "$1" \
    | grep -vE '^\s*(#|$)' \
    | grep -oE '/opt/5hostachy/[A-Za-z0-9_.-]+\.sh' \
    | sed 's#.*/##' | sort -u | paste -sd, - | tr -d ' \n'
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

verdict_sondes_maintenance() {
  # $1 = âge (min) de la dernière exécution vue dans le JOURNAL du nœud
  # $2 = âge (min) du dernier rapport de ce nœud EN BASE ("" = aucun)
  # $3 = tolérance (min) entre les deux
  #
  #  DEUX SONDES INDÉPENDANTES, et c'est leur DÉSACCORD qui porte l'information
  #  (`standards/04-fiabilite-des-controles.md`). Chacune prise seule ment par
  #  omission — vécu du 09 au 11/08/2026 :
  #    - le journal disait « la maintenance a tourné » (C17, vert) ;
  #    - la base disait « aucun rapport », et l'écran affichait un badge rouge
  #      que rien ne permettait de distinguer d'une tâche qui n'a pas tourné.
  #  Les deux avaient raison : le script tournait et mourait avant d'envoyer son
  #  rapport, la rotation des journaux ayant délié son propre inode (corrigé en
  #  v2.46.8). Personne ne comparait, donc le seul symptôme était illisible.
  #
  #  Sens de la comparaison : un rapport NETTEMENT plus vieux que la dernière
  #  exécution connue signifie que la chaîne de remontée est rompue. L'inverse
  #  (rapport plus récent que le journal) n'est pas une anomalie : le rapport
  #  peut venir d'un déclenchement manuel depuis l'interface, qui n'écrit pas
  #  dans le journal du nœud.
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Base non interrogeable (standby : aucune API locale) → INCONNU, jamais OK.
  [ "$2" = "-" ] && { echo INCONNU; return; }
  #  Le journal montre une exécution, la base n'a AUCUN rapport de ce nœud.
  [ -z "$2" ] && { echo DIVERGENCE; return; }
  case "$2" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ $(( $2 - $1 )) -gt "$3" ] && echo DIVERGENCE || echo OK
}

# ── Taille du cache de build Docker en Go entiers (PURE — testable) ──────────
# `docker system df` rend « 64.68GB », « 980MB »… Rend -1 si illisible :
# INCONNU n'est jamais OK (règle 1 du CLAUDE.md).
cache_go() {  # $1 = "64.68GB" → 64 ; "980MB" → 0 ; "" → -1
  local s="$1" n u
  n=$(echo "$s" | grep -oE '^[0-9]+([.][0-9]+)?')
  u=$(echo "$s" | grep -oE '[kKMGT]?B$')
  [ -n "$n" ] && [ -n "$u" ] || { echo -1; return; }
  case "$u" in
    GB)          echo "${n%%.*}" ;;
    TB)          echo $(( ${n%%.*} * 1024 )) ;;
    MB|kB|KB|B)  echo 0 ;;
    *)           echo -1 ;;
  esac
}

# ── Verdict du cache de build (PURE — testable) ──────────────────────────────
# Args : taille en Go (-1 = illisible), seuil → "ok" | "depasse" | "inconnu".
# Séparé de la mesure pour que le CAS ZÉRO soit testable : un cache illisible
# doit rendre INCONNU et non « 0 Go, donc sous le seuil » (règle 1).
cache_verdict() {
  local go="$1" max="$2"
  case "$go" in ''|*[!0-9-]*) echo inconnu; return ;; esac
  [ "$go" -lt 0 ] && { echo inconnu; return; }
  [ "$go" -ge "$max" ] && echo depasse || echo ok
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
  echo "-- cache_go --"
  for c in "64.68GB:64" "11.16GB:11" "980MB:0" "512kB:0" "1.5TB:1024" ":-1" "n/a:-1"; do
    exp=${c##*:}; got=$(cache_go "${c%:*}")
    [ "$got" = "$exp" ] && echo "PASS  cache '${c%:*}' → $got Go" || { echo "FAIL  cache '${c%:*}' attendu=$exp obtenu=$got"; st_fail=1; }
  done
  echo "-- cache_verdict --"
  cv() { # description attendu go seuil
    local desc="$1" exp="$2"; shift 2
    local got; got=$(cache_verdict "$@")
    [ "$got" = "$exp" ] && echo "PASS  $desc  → $got" \
      || { echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; }
  }
  cv "régime normal du dimanche"        "ok"      10 "$BUILD_CACHE_WARN_GB"
  cv "régime de veille de dimanche"     "ok"      29 "$BUILD_CACHE_WARN_GB"
  cv "pile au seuil"                    "depasse" 40 "$BUILD_CACHE_WARN_GB"
  cv "purge réellement en panne"        "depasse" 64 "$BUILD_CACHE_WARN_GB"
  # Le CAS ZÉRO, celui qui a déjà fait mentir C14 le 30/07 : une mesure illisible
  # rend -1, et -1 n'est PAS « 0 Go, donc tout va bien ».
  cv "mesure illisible (-1)"            "inconnu" -1 "$BUILD_CACHE_WARN_GB"
  cv "mesure vide"                      "inconnu" "" "$BUILD_CACHE_WARN_GB"
  cv "mesure non numérique"             "inconnu" "n/a" "$BUILD_CACHE_WARN_GB"
  echo "-- cohérence seuil / politique de rétention --"
  # C'est l'erreur du 06/08/2026 mise sous garde-fou : le seuil avait été déduit
  # du plafond du dimanche (10 → 20), en oubliant que le cache regrossit six
  # nuits avant la purge suivante. Un seuil sous le régime rend le contrôle WARN
  # en permanence sur une infra saine. Si la croissance mesurée augmente, c'est
  # ce test qui doit rappeler de relever le seuil — pas un log qu'on ignore.
  REGIME=$(( BUILD_CACHE_FLOOR_GB + 6 * BUILD_CACHE_GROWTH_GB ))
  if [ "$BUILD_CACHE_WARN_GB" -gt "$REGIME" ]; then
    echo "PASS  seuil ${BUILD_CACHE_WARN_GB} Go > régime ${REGIME} Go (plafond ${BUILD_CACHE_FLOOR_GB} + 6 nuits × ${BUILD_CACHE_GROWTH_GB})"
  else
    echo "FAIL  seuil ${BUILD_CACHE_WARN_GB} Go ≤ régime ${REGIME} Go — C16 sera WARN sur une infra saine"; st_fail=1
  fi
  echo "-- crontab_scripts --"
  cs() { # description attendu crontab-brut
    local desc="$1" exp="$2"; shift 2
    local got; got=$(crontab_scripts "$1")
    [ "$got" = "$exp" ] && echo "PASS  $desc  → '$got'" \
      || { echo "FAIL  $desc  attendu='$exp' obtenu='$got'"; st_fail=1; }
  }
  #  Les redirections des fixtures respectent le motif des logs rotés : le job CI
  #  `test-scripts` scanne TOUS les .sh à la recherche d'un chemin de journal que
  #  `maintenance.sh` ne roterait pas, et il ne distingue — à raison — ni le code
  #  de la donnée de test, ni le code du commentaire. Des fixtures avec un nom
  #  court et arbitraire le faisaient donc échouer ; attrapé en rejouant la CI en
  #  local, pas en s'en souvenant.
  cs "deux tâches, triées" "bascule.sh,maintenance.sh" \
"0 3 * * 0 /opt/5hostachy/maintenance.sh >> /var/log/hostachy-maintenance.log 2>&1
0 2 * * * /opt/5hostachy/bascule.sh >> /var/log/hostachy-bascule.log 2>&1"
  cs "commentaires et lignes vides ignorés" "health-watch.sh" \
"# Health check toutes les 5 min

2,7 * * * * /opt/5hostachy/health-watch.sh >> /var/log/hostachy-health-watch.log 2>&1"
  #  Le cas qui a motivé C18 : le même crontab, plus une entrée d'un seul côté.
  cs "le script en trop apparaît" "bascule.sh,check-stack.sh" \
"0 2 * * * /opt/5hostachy/bascule.sh
4,14 * * * * /opt/5hostachy/check-stack.sh >> /var/log/hostachy-check.log 2>&1"
  #  Une ligne COMMENTÉE ne compte pas : désactiver un cron doit se voir comme un
  #  retrait, sinon le contrôle dirait « identiques » sur deux nœuds qui diffèrent.
  cs "entrée commentée non comptée" "bascule.sh" \
"0 2 * * * /opt/5hostachy/bascule.sh
#4,14 * * * * /opt/5hostachy/check-stack.sh"
  #  Cas ZÉRO : crontab illisible ou vide → chaîne vide, que C18 traite en INCONNU
  #  et jamais en « identiques » (deux vides seraient égaux — le piège exact).
  cs "crontab vide" "" ""
  cs "crontab sans tâche 5Hostachy" "" "0 5 * * * /usr/bin/autre-chose"
  echo "-- âge de maintenance (réutilise beat_age_min/beat_verdict) --"
  check "maintenance de 4 j"                    "ok"      5760  "$MAINT_MAX_AGE_MIN"
  check "maintenance pile à 8 j"                "ok"      11520 "$MAINT_MAX_AGE_MIN"
  check "deux dimanches manqués"                "absent"  20160 "$MAINT_MAX_AGE_MIN"
  check "maintenance jamais horodatée"          "inconnu" -1    "$MAINT_MAX_AGE_MIN"
  echo "-- C19 : le journal et la base disent-ils la même chose ? --"
  sm() {  # $1 = libellé, $2 = attendu, $3 = âge journal, $4 = âge base, $5 = tolérance
    r=$(verdict_sondes_maintenance "$3" "$4" "$5")
    if [ "$r" = "$2" ]; then echo "PASS  $1 → $r"
    else echo "FAIL  $1  attendu=$2 obtenu=$r"; st_fail=1; fi
  }
  #  Le cas vécu : la maintenance a tourné il y a 2 j, aucun rapport en base.
  sm "a tourné, aucun rapport (09-11/08)"  DIVERGENCE 2880 ""    720
  sm "rapport aussi vieux que l'exécution" OK         2880 2880  720
  sm "rapport en retard mais dans la marge" OK        2880 3300  720
  sm "rapport bien plus vieux que la course" DIVERGENCE 2880 5760 720
  #  Un déclenchement manuel depuis l'interface n'écrit pas dans le journal :
  #  un rapport PLUS RÉCENT que la dernière ligne du journal est normal.
  sm "rapport plus récent que le journal"  OK         2880 60    720
  #  Standby : aucune API locale, la base n'est pas interrogeable depuis ce nœud.
  sm "base non interrogeable (standby)"    INCONNU    2880 "-"   720
  sm "journal illisible"                   INCONNU    ""   2880  720
  sm "âge journal aberrant"                INCONNU    "x"  2880  720
  sm "âge base aberrant"                   INCONNU    2880 "hier" 720
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
echo "buildcache=$(docker system df --format "{{.Type}}|{{.Size}}" 2>/dev/null | grep -i "^Build Cache" | cut -d"|" -f2 | tr -d " ")"
# Motif SANS accent volontairement : ce bloc traverse SSH, et « Hygiène » y
# dépendrait de la locale des deux bouts. « Garde-fou » est aussi distinctif.
echo "maint_last=$(grep "Garde-fou" '"$MAINT_LOG"' 2>/dev/null | grep -oE "^\[[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}\]" | tail -1 | tr -d "[]")"
# Date du dernier rapport de maintenance EN BASE, pour ce nœud — la seconde sonde
# de C19. Lue par l'\''API in-process (jamais en ouvrant app.db : règle d'\''or), donc
# elle ne répond que sur l'\''ACTIF. Sur le standby la chaîne est vide, et C19 le
# traduit en INCONNU au lieu de conclure à une divergence.
MK=$(grep -E "^MAINTENANCE_KEY=" '"$R"'/.env 2>/dev/null | cut -d= -f2- | tr -d "\"'"'"' \r")
if [ -n "$MK" ]; then
  echo "rapports=$(curl -s --max-time 8 -H "x-maintenance-key: $MK" \
    "http://localhost/api/admin/maintenance/dernier-rapport?tache=maintenance" 2>/dev/null \
    | grep -oE "\"rpi[0-9]\": ?\"[0-9T:.-]+\"" | tr -d "\" " | tr "\n" ";")"
else
  echo "rapports="
fi
# Crontab ROOT, et root seulement. Le test sur l'\''uid n'\''est pas une précaution
# de style : ce bloc tourne en root en local (cron root) mais en `ptressard` sur le
# peer (SSH). Un `crontab -l` nu y rendrait le crontab de `ptressard` — qui existe,
# donc la commande RÉUSSIRAIT en donnant la mauvaise réponse. Un faux vert par
# succès, le pire des cas.
if [ "$(id -u)" = "0" ]; then CRONRAW=$(crontab -l 2>/dev/null); else CRONRAW=$(sudo -n crontab -l 2>/dev/null); fi
echo "cronscripts=$(echo "$CRONRAW" | grep -vE "^\s*(#|$)" | grep -oE "/opt/5hostachy/[A-Za-z0-9_.-]+\.sh" | sed "s#.*/##" | sort -u | paste -sd, - | tr -d " \n")"
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

# ── C16. Cache de build Docker sous plafond ──────────────────────────────────
# `docker image prune` ne touche PAS le cache BuildKit, et rien ne le purgeait :
# 64 Go sur rpi1 (disque à 66 %) et 59 Go sur rpi2 le 31/07/2026, accumulés à
# raison d'un rebuild du peer par nuit depuis la v2.20.19. maintenance.sh le
# plafonne désormais à 10 Go chaque dimanche ; ce contrôle attrape la panne de
# cette purge, des mois avant que C9 (disque ≥ 85 %) ne s'en aperçoive — et sans
# faire croire à une fuite applicative, comme un simple « disque à 85 % ».
#
# Le seuil est calculé sur la politique de rétention, pas sur le plafond (voir le
# bloc BUILD_CACHE_* en tête). Et le message ne DÉSIGNE PLUS DE CAUSE : il disait
# « la purge hebdomadaire ne fait plus son travail », ce qui envoyait déboguer
# maintenance.sh alors qu'elle avait purgé quatre jours plus tôt. Un dépassement
# a plusieurs causes possibles — purge en panne, croissance plus rapide que
# prévu, semaine chargée en rebuilds — et ce contrôle ne sait pas laquelle.
# Il rapporte ce qu'il mesure et renvoie vers ce qui, lui, sait : C17.
for pair in "$SELF:${S_buildcache:-}" "$PEER:${P_buildcache:-}"; do
  n=${pair%%:*}; v=${pair#*:}; [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
  g=$(cache_go "$v")
  case "$(cache_verdict "$g" "$BUILD_CACHE_WARN_GB")" in
    ok)      ok "Cache de build Docker à ${g} Go sur $n (< ${BUILD_CACHE_WARN_GB})" ;;
    depasse) warn "Cache de build Docker à ${g} Go sur $n (≥ ${BUILD_CACHE_WARN_GB}, régime attendu ≤ $(( BUILD_CACHE_FLOOR_GB + 6 * BUILD_CACHE_GROWTH_GB )) Go) — vérifier C17 avant de conclure à une purge en panne" ;;
    *)       warn "Cache de build Docker INCONNU sur $n ('${v:-vide}' illisible) — ni vert ni rouge : la mesure a échoué" ;;
  esac
done

# ── C17. La maintenance hebdomadaire a-t-elle tourné, sur les DEUX nœuds ? ────
# C16 ne mesurait la santé de la purge que par la TAILLE du cache — un proxy
# confondu par la croissance normale, ce qui l'a rendu WARN 4 jours sur 7 (voir
# son commentaire). Le fait lui-même n'était mesuré nulle part en continu : il
# n'existait qu'au point 14 du pré-check, donc seulement les jours de MEP, alors
# que l'invariant est permanent (règle 2 du CLAUDE.md).
#
# Ce contrôle mesure donc directement CE QUI COMPTE : la date de la dernière
# exécution de l'hygiène. Sur les deux nœuds, parce que le défaut du 31/07/2026
# était précisément que maintenance.sh ne tournait que sur l'actif, et qu'un nœud
# n'est actif qu'un dimanche sur deux — le standby dérivait sans que rien ne le
# dise (80 218 lignes dans hostachy-check.log sur rpi2).
#
# WARN et non FAIL : une maintenance en retard ne coupe pas la production, elle
# la laisse se dégrader. Ce qui coupe, C9 et C10 le voient déjà.
for pair in "$SELF:${S_maint_last:-}" "$PEER:${P_maint_last:-}"; do
  n=${pair%%:*}; v=${pair#*:}; [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
  MAINT_AGE=$(beat_age_min "$v")
  MAINT_D=$(( MAINT_AGE / 1440 ))
  case "$(beat_verdict "$MAINT_AGE" "$MAINT_MAX_AGE_MIN")" in
    ok)      ok "Maintenance hebdomadaire sur $n : dernière exécution il y a ${MAINT_D} j" ;;
    absent)  warn "Maintenance hebdomadaire en retard sur $n : dernière exécution il y a ${MAINT_D} j (attendu ≤ $(( MAINT_MAX_AGE_MIN / 1440 )) j) → cron root perdu, bit x, ou script en erreur avant l'hygiène" ;;
    *)       warn "Maintenance hebdomadaire INCONNUE sur $n : aucune ligne horodatée 'Garde-fou' dans $MAINT_LOG (jamais exécutée, log illisible, ou format changé)" ;;
  esac
done

# ── C18. Les crontabs root portent-ils les MÊMES scripts sur les 2 nœuds ? ────
# `CLAUDE.md` annonce « Cron root (identique sur les 2 nœuds) ». C'était faux, et
# personne ne pouvait le savoir : rpi2 portait en plus `check-stack.sh`, planifié
# toutes les 10 min, qui y échouait à CHAQUE passage — le port 8080 est tenu par
# l'application co-hébergée — soit 144 échecs par jour dans un log que rien ne lit.
# Sur rpi1, où le port est libre, il n'était pas planifié du tout : la couverture
# réelle était nulle des deux côtés, à l'inverse l'un de l'autre. Retiré du cron le
# 06/08/2026, redevenu l'outil ponctuel que son en-tête décrit.
#
# La leçon n'est pas « il y avait un script en trop », c'est qu'une **phrase de
# documentation tenait lieu de garantie**. Une divergence de crontab est invisible :
# chaque nœud a l'air normal vu de lui-même, et il faut comparer pour voir quoi que
# ce soit. D'où ce contrôle, qui est la seule chose qui rend la phrase vraie.
if [ "$PEER_OK" -eq 0 ]; then
  if [ -z "${S_cronscripts:-}" ] || [ -z "${P_cronscripts:-}" ]; then
    warn "Crontabs root INCONNUS (${SELF}='${S_cronscripts:-vide}' ${PEER}='${P_cronscripts:-vide}') — comparaison impossible, ni vert ni rouge"
  elif [ "$S_cronscripts" = "$P_cronscripts" ]; then
    ok "Crontabs root identiques sur les 2 nœuds ($S_cronscripts)"
  else
    warn "Crontabs root DIVERGENTS — $SELF='$S_cronscripts' vs $PEER='$P_cronscripts' : un script planifié d'un seul côté ne tourne qu'un jour sur deux, ou échoue en silence là où il ne peut pas fonctionner"
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
      "$(printf 'check-reliability.sh sur %s a relevé %s FAIL et %s WARN à %s.\n\nDétail (cette exécution) :\n%s\nLog complet : /var/log/hostachy-reliability.log\n' \
          "$SELF" "$FAILS" "$WARNS" "$(date '+%d/%m/%Y %H:%M')" "$FAIL_LINES")"
  else
    echo "[WARN] lib-alert.sh introuvable dans $REPO — aucune alerte envoyée."
  fi
fi

# ── C19. Le journal et la base disent-ils la même chose de la maintenance ? ───
# C17 lit le JOURNAL du nœud et sait si la maintenance a tourné. L'écran
# d'administration lit la BASE et sait si son rapport est arrivé. Du 09 au
# 11/08/2026 les deux se sont contredits pendant trois jours sans que rien ne le
# signale : C17 était vert, l'écran affichait « Aucun rapport reçu » en rouge, et
# ce badge était indiscernable de celui d'une tâche qui n'aurait jamais tourné.
#
# Les deux disaient vrai. Le script tournait et mourait AVANT d'envoyer son
# rapport : la rotation des journaux déliait son propre inode (corrigé en
# v2.46.8, mais 11 h après le dernier passage hebdomadaire). Aucune des deux
# sondes ne pouvait le dire seule — c'est leur DÉSACCORD qui portait
# l'information, et personne ne les comparait.
#
# Ce contrôle est donc la sonde manquante : il ne mesure rien de neuf, il
# confronte deux mesures existantes (`standards/04-fiabilite-des-controles.md`,
# deux sondes indépendantes avant de conclure).
#
# WARN et non FAIL : une remontée cassée ne coupe pas la production, elle rend
# la surveillance aveugle. Ce qui coupe, C9 et C10 le voient déjà.
C19_TOLERANCE_MIN=720          # 12 h : le rapport part en fin de maintenance,
                               # elle-même longue de quelques minutes.
for pair in "$SELF:${S_maint_last:-}" "$PEER:${P_maint_last:-}"; do
  n=${pair%%:*}; v=${pair#*:}
  [ "$n" = "$PEER" ] && [ "$PEER_OK" -ne 0 ] && continue
  AGE_J=$(beat_age_min "$v")
  #  `rapports` n'est renseigné que par le nœud qui porte l'API (l'actif) : la
  #  carte qu'il rend couvre LES DEUX nœuds, puisque le standby lui poste ses
  #  propres rapports. Si aucun des deux n'a pu l'obtenir, la base est
  #  ininterrogeable → « - », que la fonction traduit en INCONNU.
  CARTE="${S_rapports:-}${P_rapports:-}"
  if [ -z "$CARTE" ]; then
    AGE_B="-"
  else
    D=$(echo "$CARTE" | tr ';' '
' | grep -oE "^$n:[0-9-]{10}T[0-9:]{8}" | head -1 | cut -d: -f2- | tr 'T' ' ')
    AGE_B=$(beat_age_min "$D")
    [ "$AGE_B" = "-1" ] && AGE_B=""      # aucune ligne pour ce nœud
  fi
  case "$(verdict_sondes_maintenance "$AGE_J" "$AGE_B" "$C19_TOLERANCE_MIN")" in
    OK)         ok "Maintenance sur $n : le journal et la base concordent" ;;
    DIVERGENCE) warn "Maintenance sur $n : elle a TOURNÉ (journal) mais son rapport n'est pas arrivé en base — la chaîne de remontée est rompue, l'écran d'administration affichera « Aucun rapport reçu » à tort" ;;
    *)          warn "Maintenance sur $n : concordance journal/base INCONNUE (journal='${AGE_J}' base='${AGE_B}') — ni vert ni rouge" ;;
  esac
done

exit "$FAILS"
