#!/usr/bin/env bash
# =============================================================================
#  Pré-check MEP 15 points — exécutable, et non plus une liste à dérouler à la main.
#
#  POURQUOI ce script existe. La grille des 15 points vit dans
#  `.claude/skills/mep-precheck` depuis le 02/08/2026, et l'ordre des opérations
#  (pré-check AVANT le push sur dev) dans la banque de mémoire du projet. Les deux
#  étaient justes. Ils ont quand même été enfreints TROIS lots d'affilée les 07 et
#  08/08/2026, au motif que « s'arrêter au push dev » dispenserait du pré-check —
#  alors que `auto-deploy.sh` déploie `origin/main` toutes les 5 minutes : fusionner
#  la PR EST la mise en production.
#
#  C'est la troisième récidive du même défaut de discipline (socle 01 §2). La
#  conclusion du socle s'applique à elle-même : une consigne ne se maintient pas
#  seule. D'où ce script, et le hook `.githooks/pre-push` qui exige sa trace.
#
#  RÈGLES DE CONCEPTION (socle 04) :
#   - un contrôle qui ne peut pas s'exécuter rend INCONNU, jamais OK ;
#   - une sortie vide n'est pas un vert ;
#   - jamais `$(grep -c … || echo 0)` : `grep -c` écrit déjà 0 ET sort en 1, le
#     `||` ajoute une seconde valeur et le test devient inexploitable ;
#   - jamais `docker exec` ni `sqlite3` sur app.db pendant que l'API tourne.
#
#  Usage : bash precheck-mep.sh            # déroule les 15 points
#          bash precheck-mep.sh --selftest # éprouve les fonctions de décision
# =============================================================================
set -uo pipefail

SITE="${SITE:-https://5hostachy.fr}"
RPI1="${RPI1:-ptressard@192.168.1.222}"
RPI2="${RPI2:-ptressard@192.168.1.223}"
MARQUEUR="${MARQUEUR:-.git/precheck-mep.ok}"

#: Seuils, tous nommés — un nombre nu dans un test est un seuil qu'on ne peut pas
#: discuter. Cf. socle 04 §18 : un seuil se règle sur le RÉGIME de ce qu'il surveille.
CACHE_BUILD_MAX_GB=40      # régime stationnaire ≈ 29 Go (plafond 10 + 6 nuits × 3,1)
LOG_MAX_MO=5
BATTEMENT_DEPLOY_MIN=20    # auto-deploy écrit ~12 lignes/h sur le standby

# ── Fonctions de décision, PURES et sous self-test ───────────────────────────

verdict_http() {           # $1 = code HTTP observé
  case "$1" in
    200) echo OK ;;
    000|"") echo INCONNU ;;
    *) echo FAIL ;;
  esac
}

verdict_role() {           # $1/$2 = .active des 2 nœuds, $3/$4 = nb conteneurs
  local a1=$1 a2=$2 c1=$3 c2=$4
  [ -z "$a1" ] || [ -z "$a2" ] || [ -z "$c1" ] || [ -z "$c2" ] && { echo INCONNU; return; }
  [ "$a1" != "$a2" ] && { echo FAIL; return; }          # flags divergents
  [ "$c1" -gt 0 ] && [ "$c2" -gt 0 ] && { echo FAIL; return; }   # split-brain
  [ "$c1" -eq 0 ] && [ "$c2" -eq 0 ] && { echo FAIL; return; }   # personne ne sert
  #  Le flag doit désigner le nœud qui porte réellement les conteneurs.
  if [ "$c1" -gt 0 ]; then [ "$a1" = "rpi1" ] && echo OK || echo FAIL
  else [ "$a1" = "rpi2" ] && echo OK || echo FAIL
  fi
}

verdict_standby() {       # $1 = .active (qui DIT être l'actif), $2/$3 = conteneurs rpi1/rpi2
  #  Le standby est désigné par le DRAPEAU, pas supposé. Première version : elle
  #  vérifiait « rpi2 porte 0 conteneur », en dur — donc elle criait au split-brain
  #  le lendemain matin, la bascule de 02:00 ayant fait de rpi2 l'actif (09/08/2026).
  #  Un contrôle qui suppose lequel des deux nœuds est actif ne survit pas à la
  #  première bascule, c'est-à-dire à une nuit.
  [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ] && { echo INCONNU; return; }
  case "$2$3" in (*[!0-9]*) echo INCONNU; return ;; esac
  if [ "$1" = "rpi1" ]; then [ "$3" -eq 0 ] && echo OK || echo FAIL
  elif [ "$1" = "rpi2" ]; then [ "$2" -eq 0 ] && echo OK || echo FAIL
  else echo INCONNU; fi
}

verdict_compte() {         # $1 = nombre observé, $2 = maximum toléré
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ "$1" -le "$2" ] && echo OK || echo FAIL
}

verdict_parite() {         # $1/$2 = HEAD des 2 nœuds
  [ -z "$1" ] || [ -z "$2" ] && { echo INCONNU; return; }
  [ "$1" = "$2" ] && echo OK || echo ECART   # écart = toléré, resync à la bascule
}

verdict_age_min() {        # $1 = âge en minutes, $2 = âge maximum
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ "$1" -le "$2" ] && echo OK || echo FAIL
}

verdict_cache() {          # $1 = taille brute rendue par docker system df (ex. « 25.26GB »)
  #  ⚠️ Ne JAMAIS lire la 3ᵉ colonne de `docker system df` : pour « Build Cache »,
  #  le type tient en deux mots, donc $3 est le NOMBRE D'ENTRÉES (589 le 08/08) et
  #  non la taille. Mesuré ainsi, le contrôle annonçait « 589 Go » sur un disque qui
  #  n'en fait pas tant — un faux échec produit par le contrôle lui-même.
  [ -z "$1" ] && { echo INCONNU; return; }
  #  ⚠️ L'ordre compte : `*B` capture aussi « 64.1GB ». Le gigaoctet se teste
  #  D'ABORD, sinon tout cache passe pour un cache minuscule — le self-test a
  #  attrapé cette inversion avant la première exécution réelle.
  case "$1" in
    *GB) : ;;
    *MB|*kB|*B) echo OK; return ;;                       # sous le gigaoctet
    *) echo INCONNU; return ;;
  esac
  local go=${1%GB}; go=${go%%.*}
  case "$go" in (*[!0-9]*|"") echo INCONNU; return ;; esac
  [ "$go" -lt "$CACHE_BUILD_MAX_GB" ] && echo OK || echo FAIL
}

verdict_alerte() {         # $1 = âge de la dernière « Alerte envoyée », $2 = âge du dernier [FAIL]
  #  Le canal n'écrit QUE lorsqu'il a quelque chose à dire : son silence est normal
  #  s'il n'y a rien à signaler. On ne peut donc conclure qu'en croisant les deux.
  #  Les lignes « Email KO » ne servent pas : elles ne sont pas horodatées — constat
  #  du 02/08/2026, où le point a été classé INCONNU alors que l'utilisateur venait
  #  de recevoir deux alertes.
  [ -z "$2" ] && { echo OK; return; }                    # aucun échec → rien à envoyer
  case "$2" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ -z "$1" ] && { echo FAIL; return; }                  # un échec, aucune alerte : muet
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Cooldown d'une heure : une alerte peut légitimement suivre son échec de 60 min.
  [ "$1" -le $(( $2 + 60 )) ] && echo OK || echo FAIL
}

if [ "${1:-}" = "--selftest" ]; then
  st=0
  #  `"$@"` et non `$1 $2 …` : la découpe des mots supprimait les arguments VIDES,
  #  qui sont précisément les cas à éprouver — une mesure manquante. Le self-test
  #  a attrapé le défaut dans sa propre plomberie avant de servir une seule fois.
  t() {
    local libelle=$1 attendu=$2; shift 2
    local r; r=$("$@")
    if [ "$r" = "$attendu" ]; then echo "PASS  $libelle → $r"
    else echo "FAIL  $libelle  attendu=$attendu obtenu=$r"; st=1; fi
  }
  t "site qui répond"                    OK      verdict_http 200
  t "site en erreur"                     FAIL    verdict_http 503
  t "hôte injoignable"                   INCONNU verdict_http 000
  t "sortie vide n'est pas un vert"      INCONNU verdict_http ""
  t "nominal : flags d'accord"           OK      verdict_role rpi1 rpi1 4 0
  t "flags divergents (26/07)"           FAIL    verdict_role rpi2 rpi1 4 0
  t "split-brain des deux côtés"         FAIL    verdict_role rpi1 rpi1 4 3
  t "personne ne sert"                   FAIL    verdict_role rpi1 rpi1 0 0
  t "flag ment : rpi2 porte la charge"   FAIL    verdict_role rpi1 rpi1 0 4
  t "mesure manquante"                   INCONNU verdict_role "" rpi1 4 0
  t "standby vide, rpi1 actif"           OK      verdict_standby rpi1 4 0
  t "standby vide, rpi2 actif (après bascule)" OK verdict_standby rpi2 0 4
  t "standby qui porte des conteneurs"   FAIL    verdict_standby rpi1 4 3
  t "drapeau inconnu"                    INCONNU verdict_standby rpi9 4 0
  t "comptes non mesurés"                INCONNU verdict_standby rpi1 "" 0
  t "zéro erreur"                        OK      verdict_compte 0 0
  t "erreurs présentes"                  FAIL    verdict_compte 3 0
  t "compte non mesuré"                  INCONNU verdict_compte "" 0
  t "piège du grep -c || echo 0"         INCONNU verdict_compte "0 0" 0
  t "compte non numérique"               INCONNU verdict_compte "abc" 0
  t "HEAD identiques"                    OK      verdict_parite abc123 abc123
  t "standby en retard : toléré"         ECART   verdict_parite abc123 def456
  t "parité non mesurable"               INCONNU verdict_parite "" def456
  t "battement récent"                   OK      verdict_age_min 5 20
  t "battement manquant"                 FAIL    verdict_age_min 90 20
  t "âge non mesurable"                  INCONNU verdict_age_min "" 20
  t "cache sous le seuil"                OK      verdict_cache "25.26GB"
  t "cache au-dessus du seuil"           FAIL    verdict_cache "64.1GB"
  t "cache en mégaoctets"                OK      verdict_cache "812.4MB"
  t "cache non mesuré"                   INCONNU verdict_cache ""
  t "nombre d'entrées pris pour Go"      INCONNU verdict_cache "589"
  t "aucun échec : silence normal"       OK      verdict_alerte "" ""
  t "échec sans aucune alerte"           FAIL    verdict_alerte "" 30
  t "alerte postérieure à l'échec"       OK      verdict_alerte 25 30
  t "alerte dans le cooldown d'1 h"      OK      verdict_alerte 80 30
  t "échec ancien jamais alerté"         FAIL    verdict_alerte 5000 30
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st
fi

# ── Exécution ────────────────────────────────────────────────────────────────

NB_OK=0; NB_FAIL=0; NB_INCONNU=0; NB_ECART=0
rapporter() {              # $1 = numéro, $2 = verdict, $3 = libellé, $4 = détail
  local icone
  case "$2" in
    OK)      icone="✓"; NB_OK=$((NB_OK+1)) ;;
    ECART)   icone="~"; NB_ECART=$((NB_ECART+1)) ;;
    INCONNU) icone="?"; NB_INCONNU=$((NB_INCONNU+1)) ;;
    *)       icone="✗"; NB_FAIL=$((NB_FAIL+1)) ;;
  esac
  printf "%s %-3s %-46s %-8s %s\n" "$icone" "$1" "$3" "$2" "${4:-}"
}

#  Un SSH qui échoue rend une chaîne VIDE, que les fonctions de décision
#  traduisent en INCONNU — jamais en OK.
sur() { timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=8 "$1" "$2" 2>/dev/null; }

http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$1" 2>/dev/null; }

echo "═══ Pré-check MEP — $(date '+%Y-%m-%d %H:%M') ═══"
echo

# 0a — clone à jour
git fetch origin --quiet 2>/dev/null
BRANCHE=$(git rev-parse --abbrev-ref HEAD)
RETARD=$(git rev-list --count "HEAD..origin/$BRANCHE" 2>/dev/null)
rapporter 0a "$(verdict_compte "${RETARD:-}" 0)" "Clone à jour sur origin/$BRANCHE" "retard=${RETARD:-?} commit(s)"

# 0b — modularité : rejouer ici ce que la CI refusera
#      Ajouté le 08/08/2026 : trois pushes sont partis alors que le job CI
#      `test-scripts` les rejetait (email.py 656 → 663). Le contrôle existait,
#      il n'était simplement pas dans le chemin qui précède le push.
MOD=$(bash scripts-ci-modularite.sh origin/main 2>&1)
case "$?" in
  0) V0B=OK ;;
  1) V0B=FAIL ;;
  *) V0B=INCONNU ;;
esac
rapporter 0b "$V0B" "Modularité (ce que la CI vérifiera)"           "$(echo "$MOD" | grep -oE '[a-z_/.]+\.(py|sh|ts|svelte) : [0-9]+ → [0-9]+ lignes' | head -1 || echo 'aucun fichier n a grossi')"

# 15 — endpoints orphelins (poste de dev, avant le push)
if [ -d api/tests ]; then
  ORPH=$( (cd api && python -m pytest tests/test_endpoints_orphelins.py -q 2>&1 | tail -1) )
  case "$ORPH" in
    *"passed"*) V15=OK ;;
    *) V15=FAIL ;;
  esac
else
  V15=INCONNU; ORPH="répertoire api/tests introuvable"
fi
rapporter 15 "$V15" "Aucun endpoint orphelin" "$ORPH"

# 1 — site public
CODE=$(http_code "$SITE/api/health")
rapporter 1 "$(verdict_http "$CODE")" "Site public" "HTTP ${CODE:-?}"

# 2 et 3 — rôle actif cohérent, pas de split-brain
A1=$(sur "$RPI1" 'cat /opt/5hostachy/.active')
A2=$(sur "$RPI2" 'cat /opt/5hostachy/.active')
C1=$(sur "$RPI1" 'docker ps -q --filter name=hostachy | wc -l')
C2=$(sur "$RPI2" 'docker ps -q --filter name=hostachy | wc -l')
rapporter 2 "$(verdict_role "$A1" "$A2" "$C1" "$C2")" "Rôle actif cohérent et conforme au réel" \
          "rpi1='${A1:-?}'/${C1:-?}c  rpi2='${A2:-?}'/${C2:-?}c"
rapporter 3 "$(verdict_standby "${A1:-}" "${C1:-}" "${C2:-}")" "Pas de split-brain"           "actif déclaré=${A1:-?} — conteneurs rpi1=${C1:-?} rpi2=${C2:-?}"

#  L'actif est déduit du réel, pas du flag : c'est lui qui porte les conteneurs.
if [ "${C1:-0}" != "0" ]; then ACTIF="$RPI1"; STANDBY="$RPI2"; else ACTIF="$RPI2"; STANDBY="$RPI1"; fi

# 4 — DB saine, SANS ouvrir app.db ni sudo
WAL=$(sur "$ACTIF" 'docker run --rm -v 5hostachy_app_data:/data:ro python:3.12-slim \
      ls /data/app.db-wal /data/app.db-shm 2>/dev/null | wc -l')
IO=$(sur "$ACTIF" 'docker logs hostachy_api --since 1h 2>&1 | grep -c "disk I/O error"; true')
if [ -z "$WAL" ]; then V4=INCONNU
elif [ "$WAL" -lt 2 ]; then V4=FAIL          # WAL/SHM unlinkés = signature de corruption
else V4=$(verdict_compte "${IO:-}" 0); fi
rapporter 4 "$V4" "Base saine (WAL présent, 0 disk I/O error)" "wal+shm=${WAL:-?}  io=${IO:-?}"

# 5 — WhatsApp : dernière connexion postérieure à la dernière fermeture
WA=$(sur "$ACTIF" 'docker logs hostachy_whatsapp --since 24h 2>&1 | grep -oE "WhatsApp connected|Connection closed" | tail -1')
case "$WA" in
  "WhatsApp connected") V5=OK ;;
  "") V5=INCONNU ;;
  *) V5=FAIL ;;
esac
rapporter 5 "$V5" "Bridge WhatsApp connecté" "dernier état : ${WA:-?}"

# 6 — erreurs API
ERR=$(sur "$ACTIF" 'docker logs hostachy_api --since 1h 2>&1 | grep -cE "ERROR|CRITICAL"; true')
rapporter 6 "$(verdict_compte "${ERR:-}" 0)" "Aucune ERROR/CRITICAL (1 h)" "compte=${ERR:-?}"

# 7 — bits d'exécution des scripts lancés par cron
SANSX=$(sur "$ACTIF" 'ls -l /opt/5hostachy/*.sh 2>/dev/null | grep -v "^-rwx" | grep -cv "lib-"; true')
rapporter 7 "$(verdict_compte "${SANSX:-}" 0)" "Scripts cron exécutables" "sans bit x=${SANSX:-?}"

# 8 — battement d'auto-deploy sur le STANDBY (sur l'actif, le silence est normal)
AGE=$(sur "$STANDBY" 'd=$(grep -oE "^\[[0-9-]+ [0-9:]+" /var/log/hostachy-deploy.log 2>/dev/null | tail -1 | tr -d "["); \
      [ -n "$d" ] && echo $(( ( $(date +%s) - $(date -d "$d" +%s) ) / 60 ))')
rapporter 8 "$(verdict_age_min "${AGE:-}" $BATTEMENT_DEPLOY_MIN)" "Battement auto-deploy (standby)" \
          "dernier battement il y a ${AGE:-?} min"

# 9 — e-mails en échec : in-process uniquement, donc hors de portée d'ici
rapporter 9 INCONNU "E-mails sans échec récent" "exige une session admin — Admin → E-mails → Historique"

# 10 — parité de code entre les 2 nœuds
H1=$(sur "$RPI1" 'git -C /opt/5hostachy rev-parse --short HEAD')
H2=$(sur "$RPI2" 'git -C /opt/5hostachy rev-parse --short HEAD')
rapporter 10 "$(verdict_parite "$H1" "$H2")" "Parité de code actif ⇆ standby" \
          "rpi1=${H1:-?} rpi2=${H2:-?} (écart résorbé à la bascule de 02:00)"

# 11 — auto-deploy de l'actif vivant
PROPRIO=$(sur "$ACTIF" 'stat -c %U /var/log/hostachy-deploy.log 2>/dev/null')
if [ "$PROPRIO" = "ptressard" ]; then V11=OK; elif [ -z "$PROPRIO" ]; then V11=INCONNU; else V11=FAIL; fi
rapporter 11 "$V11" "Auto-deploy de l'actif vivant" "log appartient à ${PROPRIO:-?}"

# 12 — image du service touché reconstruite après le commit
IMG=$(sur "$ACTIF" 'docker inspect hostachy_api --format "{{.Created}}" 2>/dev/null')
CMT=$(sur "$ACTIF" 'git -C /opt/5hostachy log -1 --format=%cI 2>/dev/null')
if [ -z "$IMG" ] || [ -z "$CMT" ]; then V12=INCONNU
elif [ "$(date -d "$IMG" +%s 2>/dev/null)" -ge "$(date -d "$CMT" +%s 2>/dev/null)" ]; then V12=OK
else V12=FAIL; fi
rapporter 12 "$V12" "Image postérieure au commit déployé" "image=${IMG:0:19} commit=${CMT:0:19}"

# 13 — le canal d'alerte a-t-il émis ? On croise la dernière ALERTE et le dernier
#      ÉCHEC, tous deux horodatés. Les « Email KO » ne le sont pas : les compter
#      donnait 7 depuis toujours, indatables (mémoire du 02/08/2026).
age_ligne() {  # $1 = hôte, $2 = motif, $3 = fichier — âge en minutes, vide si absent
  sur "$1" "d=\$(grep \"$2\" $3 2>/dev/null | grep -oE '^\[[0-9-]+ [0-9:]+' | tail -1 | tr -d '[');             [ -n \"\$d\" ] && echo \$(( ( \$(date +%s) - \$(date -d \"\$d\" +%s) ) / 60 ))"
}
AGE_ALERTE=$(age_ligne "$ACTIF" "Alerte envoyée" /var/log/hostachy-reliability.log)
AGE_FAIL=$(age_ligne "$ACTIF" "^\[FAIL\]" /var/log/hostachy-reliability.log)
if [ -n "${AGE_FAIL:-}" ]; then
  DETAIL13="dernier échec il y a ${AGE_FAIL} min, alerte ${AGE_ALERTE:-jamais envoyée}"
else
  DETAIL13="aucun échec à signaler (silence normal)"
fi
rapporter 13 "$(verdict_alerte "${AGE_ALERTE:-}" "${AGE_FAIL:-}")" "Canal d'alerte non muet" "$DETAIL13"

# 14 — hygiène disque sur les DEUX nœuds
for h in "$RPI1" "$RPI2"; do
  CACHE=$(sur "$h" "docker system df 2>/dev/null | awk '/^Build Cache/ {print \$5}'")
  GROS=$(sur "$h" "find /var/log -name 'hostachy-*.log' -size +${LOG_MAX_MO}M 2>/dev/null | wc -l")
  V14=$(verdict_cache "${CACHE:-}")
  [ "$V14" = OK ] && [ -n "$GROS" ] && [ "$GROS" -gt 0 ] 2>/dev/null && V14=FAIL
  [ -z "$GROS" ] && V14=INCONNU
  rapporter 14 "$V14" "Hygiène disque (${h##*@})" "cache=${CACHE:-?}  logs>${LOG_MAX_MO}Mo=${GROS:-?}"
done

echo
echo "───────────────────────────────────────────────────────────────"
printf "OK=%d  ÉCART=%d  INCONNU=%d  ÉCHEC=%d\n" "$NB_OK" "$NB_ECART" "$NB_INCONNU" "$NB_FAIL"

if [ "$NB_FAIL" -gt 0 ]; then
  echo "✗ MEP NON AUTORISÉE — diagnostiquer les échecs, corriger, relancer."
  exit 1
fi
if [ "$NB_INCONNU" -gt 1 ]; then
  echo "? Trop de points non mesurables : un INCONNU n'est pas un vert (socle 04 §1)."
  exit 2
fi

#  Le marqueur porte le commit couvert : le hook refusera un push d'autre chose.
mkdir -p "$(dirname "$MARQUEUR")"
printf '%s %s\n' "$(git rev-parse HEAD)" "$(date +%s)" > "$MARQUEUR"
echo "✓ Pré-check passé pour $(git rev-parse --short HEAD) — push autorisé."
[ "$NB_INCONNU" -gt 0 ] && echo "  (1 point INCONNU assumé : le point 9 exige une session admin.)"
exit 0
