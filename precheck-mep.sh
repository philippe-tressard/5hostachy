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

# ── Fonctions de décision PURES ──────────────────────────────────────────────
# Extraites dans `lib-verdicts-mep.sh` le 11/08/2026 : ce fichier a dépassé 500
# lignes en recevant 0f, et son PROPRE point 0b a refusé le push. Le self-test
# est parti avec elles — il est leur contrat.
# shellcheck source=lib-verdicts-mep.sh
. "$(dirname "$0")/lib-verdicts-mep.sh"

if [ "${1:-}" = "--selftest" ]; then
  verdicts_mep_selftest
  exit $?
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
#  « Identique » = MÊME ARBRE. Un retard sur des commits dont le contenu est déjà
#  chez nous est le réalignement post-squash ; un retard sur du contenu absent est
#  la dérive que ce point existe pour attraper.
#  `origin/dev` n'apporte rien que `origin/main` n'ait déjà, ET nous descendons
#  de `origin/main` : le retard est le réalignement post-squash, pas une dérive.
if git diff --quiet "origin/$BRANCHE" origin/main 2>/dev/null    && git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then IDENT=oui; else IDENT=non; fi
if [ "${RETARD:-0}" != "0" ] && [ "$IDENT" = "oui" ]; then
  DETAIL0A="retard=$RETARD commit(s) sans apport (réalignement post-squash)"
else
  DETAIL0A="retard=${RETARD:-?} commit(s)"
fi
rapporter 0a "$(verdict_clone "${RETARD:-}" "$IDENT")" "Clone à jour sur origin/$BRANCHE" "$DETAIL0A"

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

# 0c — la CI de la BRANCHE, pas seulement celle de la PR
#      Ajouté le 09/08/2026 : j'ai annoncé « CI verte » en ne consultant que les
#      checks de la pull request, pendant que trois exécutions sur `dev`
#      échouaient. Une PR verte ne dit rien des pushes qui l'ont précédée.
#      ⚠️ Corrigé le 12/08/2026 (#318) : ce point refusait aussi le push qui
#      CORRIGE l'échec qu'il constate — on ne peut pas prouver que la CI repasse
#      sans pousser, et on ne pouvait pas pousser. La seule issue était
#      `SKIP_PRECHECK=1`, donc désarmer les vingt points pour contourner celui-ci.
#      Un échec porté par un commit dont HEAD DESCEND est dépassé par définition ;
#      les autres bloquent toujours. `echecs_bloquants` tranche, et est testée.
if command -v gh >/dev/null 2>&1; then
  #  Les runs sont rendus du PLUS RÉCENT au plus ancien — cet ordre porte la
  #  moitié de la décision, ne pas le trier.
  RUNS=$(gh run list --branch "$BRANCHE" --limit 5 --json conclusion,headSha \
           --jq '.[] | "\(.conclusion):\(.headSha)"' 2>/dev/null)
  if [ -z "${RUNS:-}" ]; then
    #  `gh` présent mais muet (hors ligne, jeton expiré), ou branche sans
    #  historique : une liste vide se lit comme « aucun échec ». On ne déduit
    #  pas un vert d'une sortie vide (socle 04 §1).
    V0C=INCONNU; DETAIL0C="aucune exécution lisible — état de la CI non mesurable"
  else
    TRIPLETS=""; NB_ECHECS=0
    for run in $RUNS; do
      concl=${run%%:*}; sha=${run#*:}
      [ "$concl" = "failure" ] && NB_ECHECS=$((NB_ECHECS + 1))
      if ! git cat-file -e "${sha}^{commit}" 2>/dev/null; then anc="?"     # absent du clone
      elif [ "$sha" = "$(git rev-parse HEAD)" ]; then anc="non"            # c est HEAD lui-même
      elif git merge-base --is-ancestor "$sha" HEAD 2>/dev/null; then anc="oui"
      else anc="non"
      fi
      TRIPLETS="$TRIPLETS ${concl}:${sha:0:7}:$anc"
    done
    RESTE=$(echecs_bloquants "$TRIPLETS")
    NB0C=${RESTE%% *}; SHAS0C=${RESTE#"$NB0C"}
    V0C=$(verdict_compte "$NB0C" 0)
    if [ "$NB0C" -gt 0 ]; then
      DETAIL0C="$NB0C échec(s) que ce lot ne corrige pas :$SHAS0C"
    elif [ "$NB_ECHECS" -gt 0 ]; then
      DETAIL0C="$NB_ECHECS échec(s), tous dépassés (succès postérieur ou corrigé ici)"
    else
      DETAIL0C="0 échec sur les 5 dernières exécutions"
    fi
  fi
else
  V0C=INCONNU; DETAIL0C="gh absent — état de la CI non mesurable"
fi
rapporter 0c "$V0C" "CI de la branche $BRANCHE" "$DETAIL0C"

# 0d — un seul bump de version par lot, et posé en dernier
#      Ajouté le 11/08/2026 sur remarque de l'utilisateur : la PR #297 portait
#      DEUX `chore(version)` — v2.49.1 puis v2.50.0 — et la v2.49.1 n'a jamais
#      été servie. J'avais bumpé en croyant le lot fini, les retours ont
#      continué, j'ai rebumpé. L'historique annonçait donc une version qui
#      n'a jamais existé en production.
#
#      Le lot = ce que la PR déposera sur `main`, donc `origin/main..HEAD`.
#      `--grep` sur le préfixe conventionnel, ancré : un commit qui MENTIONNE un
#      bump dans son corps ne doit pas être compté.
NB_BUMPS=$(git log origin/main..HEAD --grep='^chore(version)' --oneline 2>/dev/null | wc -l | tr -d ' ')
#  Le FAIT, en plus de la forme : la version qui sera SERVIE change-t-elle ?
#  Compter les commits ne le dit pas — un bump replié dans un commit fonctionnel
#  change bien la version et faisait pourtant conclure « identique » (#308).
lire_version() {  # $1 = révision git
  git show "$1:front/package.json" 2>/dev/null | grep -m1 '"version"' | cut -d'"' -f4
}
V_MAIN=$(lire_version origin/main); V_HEAD=$(lire_version HEAD)
V0D=$(verdict_bumps "${NB_BUMPS:-}" "${V_MAIN:-}" "${V_HEAD:-}")
case "$V0D" in
  OK)    D0D="${V_MAIN:-?} → ${V_HEAD:-?}$(
           [ "$NB_BUMPS" = "1" ] && echo " — $(git log origin/main..HEAD --grep='^chore(version)' --format='%s' 2>/dev/null | head -1)" \
                                 || echo " (bump replié dans un commit fonctionnel, pas de commit dédié)")" ;;
  ECART) D0D="version inchangée (${V_MAIN:-?}) : P3 ne prouvera rien" ;;
  FAIL)  D0D="$NB_BUMPS bumps — n'en garder qu'un : reset --soft puis push --force-with-lease" ;;
  *)     D0D="comptage impossible" ;;
esac
rapporter 0d "$V0D" "Un seul bump de version dans le lot" "$D0D"

# 0f — titre et descriptif de PR préparés AVANT le push
#      Ajouté le 11/08/2026, sur demande de l'utilisateur, après deux oublis dans
#      la même journée — dont le second APRÈS s'être fait reprendre sur le
#      premier. La consigne existe dans la skill `avant-commit` ; elle n'a pas
#      tenu. Même remède que 0d : un contrôle, pas un rappel.
#
#      Format attendu de `.git/pr-brief.md` — première ligne `commit: <sha>`,
#      puis le titre en `# …`, puis le corps :
#          commit: 6055161
#          # feat(admin): …
#          ### Ce qui change
#          …
BRIEF=".git/pr-brief.md"
if [ -f "$BRIEF" ]; then
  BRIEF_SHA=$(head -1 "$BRIEF" | grep -oE '[0-9a-f]{7,40}')
  BRIEF_CORPS=$(tail -n +3 "$BRIEF" | grep -cvE '^\s*$')
else
  BRIEF_SHA=""; BRIEF_CORPS=""
fi
HEAD_COURT=$(git rev-parse --short HEAD 2>/dev/null)
V0F=$(verdict_brief "${BRIEF_SHA:-}" "${HEAD_COURT:-?}" "${BRIEF_CORPS:-}")
case "$V0F" in
  OK)      D0F="$(sed -n 2p "$BRIEF" | cut -c1-60)…" ;;
  FAIL)    if [ -n "$BRIEF_SHA" ] && [ "$BRIEF_SHA" != "$HEAD_COURT" ]; then
             D0F="brief écrit pour $BRIEF_SHA, or c'est $HEAD_COURT qui part"
           else D0F="descriptif trop court ($BRIEF_CORPS ligne(s)) — un titre n'est pas un descriptif"; fi ;;
  *)       D0F="aucun $BRIEF — rédiger titre et descriptif AVANT de pousser" ;;
esac
rapporter 0f "$V0F" "Titre et descriptif de PR préparés" "$D0F"

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
#  Les deux instants s'affichent dans le MÊME référentiel — celui du poste.
#  Tronquer à 19 caractères supprimait justement ce qui portait le fuseau : le
#  `Z` de Docker (UTC) d'un côté, le `+02:00` de git (local) de l'autre. Le
#  détail montrait alors « image=…20:24:29 commit=…22:19:39 » à côté d'un verdict
#  OK — deux chiffres incomparables qui contredisaient leur propre conclusion,
#  alors que la comparaison, elle, était juste (#313). Un contrôle dont le détail
#  dément le verdict pousse à ignorer le détail.
horodate() { date -d "$1" '+%d/%m %H:%M:%S' 2>/dev/null || echo "?"; }
rapporter 12 "$V12" "Image postérieure au commit déployé" \
          "image=$(horodate "$IMG") commit=$(horodate "$CMT") (heure du poste)"

# 13 — le canal d'alerte a-t-il émis ? On croise la dernière ALERTE et le dernier
#      ÉCHEC, tous deux horodatés. Les « Email KO » ne le sont pas : les compter
#      donnait 7 depuis toujours, indatables (mémoire du 02/08/2026).
age_ligne() {  # $1 = hôte, $2 = motif, $3 = fichier — âge en minutes, vide si absent
  sur "$1" "d=\$(grep \"$2\" $3 2>/dev/null | grep -oE '^\[[0-9-]+ [0-9:]+' | tail -1 | tr -d '[');             [ -n \"\$d\" ] && echo \$(( ( \$(date +%s) - \$(date -d \"\$d\" +%s) ) / 60 ))"
}
AGE_ALERTE=$(age_ligne "$ACTIF" "Alerte envoyée" /var/log/hostachy-reliability.log)
AGE_FAIL=$(age_ligne "$ACTIF" "^\[FAIL\]" /var/log/hostachy-reliability.log)
#  Vivacité du PRODUCTEUR de FAIL. Sans elle, un script mort rend ce point vert :
#  zéro FAIL au journal se lit « rien à signaler » alors que plus rien n'écrit.
#  Vécu le 11/08/2026 — deux MEP autorisées pendant que check-reliability était
#  mort sur l'actif (#306). L'horodatage est celui de l'en-tête de chaque
#  exécution, le même repère que C15 utilise pour surveiller le peer.
CR_MAX_AGE_MIN=40   # 2 ticks de 15 min manqués, aligné sur C15
AGE_CR=$(sur "$ACTIF" "d=\$(grep -oE 'check-reliability \([0-9-]{10} [0-9:]{8}\)' /var/log/hostachy-reliability.log 2>/dev/null | tail -1 | tr -d '()' | cut -d' ' -f2-);             [ -n \"\$d\" ] && echo \$(( ( \$(date +%s) - \$(date -d \"\$d\" +%s) ) / 60 ))")
if [ -n "${AGE_FAIL:-}" ]; then
  DETAIL13="dernier échec il y a ${AGE_FAIL} min, alerte ${AGE_ALERTE:-jamais envoyée}"
elif [ -z "${AGE_CR:-}" ] || [ "${AGE_CR:-999}" -gt "$CR_MAX_AGE_MIN" ] 2>/dev/null; then
  DETAIL13="check-reliability muet depuis ${AGE_CR:-?} min — son silence ne prouve rien"
else
  DETAIL13="aucun échec à signaler, et le contrôle tourne (il y a ${AGE_CR} min)"
fi
rapporter 13 "$(verdict_alerte "${AGE_ALERTE:-}" "${AGE_FAIL:-}" "${AGE_CR:-}" "$CR_MAX_AGE_MIN")" \
          "Canal d'alerte non muet" "$DETAIL13"

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
