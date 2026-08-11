#!/bin/bash
# =============================================================================
#  lib-verdicts.sh — Fonctions de DÉCISION pures de check-reliability.sh
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`, et un bit x y serait trompeur).
#
#  POURQUOI CE FICHIER. `check-reliability.sh` a dépassé 500 lignes et le
#  garde-fou de modularité a refusé le push en y ajoutant C19 (11/08/2026), à
#  raison. La frontière n'est pas arbitraire : ces fonctions sont les seules du
#  script à être PURES — aucun SSH, aucun docker, aucune écriture, aucun sudo —
#  et ce sont exactement celles que `--selftest` éprouve. C'est le pattern
#  inauguré par `boot-role-guard.sh --selftest` (15/07/2026) : isoler la décision
#  de la collecte est le seul moyen de tester une décision d'infra sans les deux
#  RPi.
#
#  Le self-test vit ICI, avec le code qu'il éprouve : le laisser chez l'appelant
#  permettait de modifier une fonction sans relire son contrat — et c'est le
#  contrat qui dit ce que « INCONNU, jamais OK » veut dire pour chacune.
#  `bash check-reliability.sh --selftest` reste la commande ; le job CI ne change pas.
#
#  Règle pour toute fonction ajoutée ici : rendre INCONNU sur une mesure manquante
#  ou aberrante, jamais un vert (`standards/04-fiabilite-des-controles.md`).
# =============================================================================

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

# ── Contrat du module ────────────────────────────────────────────────────────
verdicts_selftest() {
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
  return $st_fail
}
