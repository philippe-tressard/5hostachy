#!/bin/bash
# =============================================================================
#  lib-verdicts-mep.sh — Fonctions de DÉCISION pures de precheck-mep.sh
#
#  Module SOURCÉ, jamais exécuté : pas de bit x (le job CI « Bits d'exécution
#  versionnés » attend 100644 sur les `lib-*.sh`).
#
#  POURQUOI. `precheck-mep.sh` a dépassé 500 lignes en recevant le point 0f
#  (11/08/2026) et son propre contrôle 0b a refusé le push — le troisième
#  découpage imposé par ce garde-fou dans la même journée, et le plus mérité :
#  c'est le fichier du pré-check qui s'est fait arrêter par le pré-check.
#
#  Même frontière que `lib-verdicts.sh` (côté check-reliability.sh) : les
#  fonctions PURES — aucun SSH, docker, écriture ni sudo — et le self-test qui
#  les éprouve, seul moyen de tester une décision de MEP sans les deux RPi.
#
#  DEUX MODULES ET NON UN SEUL, délibérément : ces deux jeux de décisions n'ont
#  aucune fonction commune et changent pour des raisons différentes (les
#  invariants d'une MEP d'un côté, ceux de la surveillance continue de l'autre).
#  Les fusionner créerait un module que deux scripts modifieraient sans se voir.
#
#  Règle pour toute fonction ajoutée ici : rendre INCONNU sur une mesure
#  manquante ou aberrante, jamais un vert (`standards/04-fiabilite-des-controles.md`).
# =============================================================================

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

#  Retard sur l'upstream : compter les commits ne suffit PAS à décider.
#  Les PR sont fusionnées en SQUASH : `main` ne partage aucun commit avec `dev`,
#  si bien que rapatrier `main` par un merge empilait tout l'historique à chaque
#  tour (30 commits affichés dans la PR du 09/08/2026). La routine est désormais
#  de RÉALIGNER `dev` sur `main` après chaque fusion — le clone est alors « en
#  retard » sur `origin/dev` sans qu'aucun contenu ne lui manque.
#
#  ⚠️ Ne PAS comparer son propre arbre à `origin/dev` : dès le premier commit
#  suivant, les arbres diffèrent légitimement et le contrôle refuse tout. Vécu
#  immédiatement après avoir écrit cette correction-là. Ce qu'il faut établir est
#  asymétrique : `origin/dev` n'apporte-t-il RIEN que nous n'ayons déjà ?
#  Deux conditions, toutes deux nécessaires :
#    • `origin/dev` et `origin/main` ont le même contenu (le retard n'est que
#      l'historique pré-squash) ;
#    • notre HEAD descend de `origin/main` (donc nous avons bien ce contenu).
#  Un contrôle qui crie au loup à chaque livraison finit contourné, et c'est le
#  contournement qui devient l'habitude (socle 04 §18).
verdict_clone() {          # $1 = commits de retard, $2 = upstream sans apport (oui/non)
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ "$1" -eq 0 ] && { echo OK; return; }
  [ "${2:-non}" = "oui" ] && echo OK || echo FAIL
}

verdict_bumps() {          # $1 = nombre de commits `chore(version)` du lot
                           # $2 = version dans origin/main · $3 = version dans HEAD
  #  Un lot porte UN bump, et un seul, posé en DERNIER.
  #
  #  Le 11/08/2026, la PR #297 en portait deux : `bump v2.49.1` puis
  #  `bump v2.50.0`. La v2.49.1 n'a JAMAIS été servie — j'avais bumpé en croyant
  #  le lot fini, les retours ont continué, j'ai rebumpé par-dessus. L'historique
  #  annonce donc une version qui n'a jamais existé en production : un commit qui
  #  décrit un fait faux, comme la PR vide de la #294.
  #
  #  La consigne « commit dédié » existait déjà et n'a pas suffi : elle ne disait
  #  pas « un seul, et en dernier ». Quand le lot repart, la conduite est de
  #  RÉÉCRIRE le bump (reset --soft puis push --force-with-lease), pas d'en
  #  empiler un second — `dev` n'est pas protégée et le force-push y est déjà le
  #  geste normal après chaque squash.
  #
  #  ZÉRO n'est pas un échec mais un ÉCART : un lot sans bump se déploie quand
  #  même, et c'est P3 qui devient incapable de prouver que le déploiement a eu
  #  lieu — la version servie serait identique avant et après. Visible, toléré.
  #
  #  ⚠️ $2 et $3 ajoutés le 11/08/2026 (#308). Compter les commits `chore(version)`
  #  mesure le SYMPTÔME attendu — la forme du message — et non le FAIT : la
  #  version qui sera servie. Un bump replié dans un commit fonctionnel faisait
  #  donc répondre « aucun bump : la version servie sera identique », phrase
  #  fausse alors que `front/package.json` passait bien de 2.52.1 à 2.52.2.
  #  C'est la règle 3 de la skill `mep-precheck`, enfreinte par un point du
  #  pré-check. La forme reste contrôlée — DEUX bumps restent un échec, c'est le
  #  défaut d'origine — mais le zéro se juge désormais sur les versions elles-mêmes.
  [ -z "$1" ] && { echo INCONNU; return; }
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Deux bumps ou plus : défaut de forme, tranché avant tout le reste.
  [ "$1" -ge 2 ] && { echo FAIL; return; }
  #  Versions non mesurables → INCONNU, jamais un vert par défaut.
  { [ -z "$2" ] || [ -z "$3" ]; } && { echo INCONNU; return; }
  #  Le FAIT : la version servie change-t-elle ? Si oui, P3 pourra le prouver,
  #  que le bump ait eu son commit dédié ou non.
  [ "$2" != "$3" ] && { echo OK; return; }
  #  Versions identiques : P3 ne pourra rien prouver. Y compris avec UN commit
  #  `chore(version)` — un bump annoncé qui ne change pas la version est le même
  #  mensonge que la PR vide de la #294, pas un vert.
  echo ECART
}

verdict_brief() {          # $1 = commit du brief, $2 = HEAD, $3 = lignes de corps
  #  Le titre et le descriptif de PR doivent être PRÉPARÉS avant le push, pas
  #  fournis quand on les réclame.
  #
  #  La skill `avant-commit` le prescrit noir sur blanc — « ne pas s'arrêter au
  #  push : enchaîner le titre et le corps de PR sans attendre qu'on les
  #  demande » — et je l'ai oublié DEUX fois le 11/08/2026, la seconde après
  #  m'être fait reprendre sur la première. C'est la démonstration, à trois jours
  #  d'intervalle du même constat sur le bump de version, qu'une consigne écrite
  #  ne se maintient pas seule : seul un contrôle qui échoue le fait.
  #
  #  Le brief est daté par le COMMIT auquel il se rapporte, comme la trace du
  #  pré-check elle-même. Sans cela, un brief rédigé pour le lot précédent
  #  passerait le contrôle en décrivant autre chose — le faux vert par fichier
  #  périmé, cousin de la liste d'exceptions qui ne pourrit pas.
  [ -z "$1" ] && { echo INCONNU; return; }        # brief absent ou illisible
  [ "$1" != "$2" ] && { echo FAIL; return; }      # brief d'un autre lot
  case "$3" in ''|*[!0-9]*) echo INCONNU; return ;; esac
  #  Cinq lignes : de quoi porter un « ce qui change » et un « pourquoi ». En
  #  dessous, ce n'est pas un descriptif, c'est un titre répété.
  [ "$3" -ge 5 ] && echo OK || echo FAIL
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
                           # $3 = âge de la dernière EXÉCUTION de check-reliability
                           # $4 = âge maximal toléré pour $3
  #  Le canal n'écrit QUE lorsqu'il a quelque chose à dire : son silence est normal
  #  s'il n'y a rien à signaler. On ne peut donc conclure qu'en croisant les deux.
  #  Les lignes « Email KO » ne servent pas : elles ne sont pas horodatées — constat
  #  du 02/08/2026, où le point a été classé INCONNU alors que l'utilisateur venait
  #  de recevoir deux alertes.
  #
  #  ⚠️ $3 et $4 ajoutés le 11/08/2026 (#306). Le silence a DEUX causes : « rien à
  #  signaler » et « le producteur de FAIL ne tourne plus ». Pendant les 2 h 15 où
  #  check-reliability était mort sur l'actif, ce point a répondu OK deux fois de
  #  suite — zéro FAIL au journal, donc rien à envoyer, donc tout va bien. Il a
  #  autorisé deux MEP en affirmant que le canal d'alerte allait bien, alors que
  #  ce qui l'alimente n'existait plus. Un contrôle qui ne peut pas s'exécuter
  #  rend INCONNU, jamais OK — c'est la première règle de la skill `mep-precheck`,
  #  et c'est un point du pré-check qui l'enfreignait.
  #
  #  La vivacité ne conditionne QUE la conclusion tirée du silence : un échec déjà
  #  écrit prouve que le producteur a tourné, et la suite garde sa logique.
  if [ -z "$2" ]; then
    [ -z "$3" ] && { echo INCONNU; return; }
    case "$3" in (*[!0-9]*) echo INCONNU; return ;; esac
    { [ -z "$4" ] || case "$4" in (*[!0-9]*) true ;; (*) false ;; esac; } && { echo INCONNU; return; }
    [ "$3" -gt "$4" ] && { echo INCONNU; return; }        # producteur muet : on ne sait pas
    echo OK; return                                       # producteur vivant, rien à signaler
  fi
  case "$2" in (*[!0-9]*) echo INCONNU; return ;; esac
  [ -z "$1" ] && { echo FAIL; return; }                  # un échec, aucune alerte : muet
  case "$1" in (*[!0-9]*) echo INCONNU; return ;; esac
  #  Cooldown d'une heure : une alerte peut légitimement suivre son échec de 60 min.
  [ "$1" -le $(( $2 + 60 )) ] && echo OK || echo FAIL
}

# ── Contrat du module ────────────────────────────────────────────────────────
verdicts_mep_selftest() {
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
  t "un seul bump, le cas nominal"       OK      verdict_bumps 1 2.52.1 2.52.2
  t "deux bumps (PR #297, 11/08)"        FAIL    verdict_bumps 2 2.52.1 2.52.2
  t "cinq bumps"                         FAIL    verdict_bumps 5 2.52.1 2.52.2
  t "aucun bump : P3 ne prouvera rien"   ECART   verdict_bumps 0 2.52.1 2.52.1
  t "comptage impossible"                INCONNU verdict_bumps ""  2.52.1 2.52.2
  t "comptage aberrant"                  INCONNU verdict_bumps "deux" 2.52.1 2.52.2
  #  ── #308 : le FAIT, pas la forme du message de commit ─────────────────────
  #  Le cas vécu : bump replié dans un commit `fix(admin)`. 0d comptait zéro
  #  commit `chore(version)` et annonçait « la version servie sera identique »,
  #  alors que package.json passait de 2.52.1 à 2.52.2.
  t "bump replié dans un commit métier"  OK      verdict_bumps 0 2.52.1 2.52.2
  #  Un bump ANNONCÉ qui ne change rien reste un écart : P3 ne prouvera rien.
  t "commit de bump sans changement"     ECART   verdict_bumps 1 2.52.1 2.52.1
  t "version amont non mesurée"          INCONNU verdict_bumps 0 ""     2.52.2
  t "version locale non mesurée"         INCONNU verdict_bumps 0 2.52.1 ""
  #  La forme prime sur le fait dans un seul sens : deux bumps restent un échec
  #  même si la version finit par changer — c'est le défaut d'origine (#297).
  t "deux bumps malgré version changée"  FAIL    verdict_bumps 2 2.52.1 2.53.0
  t "brief du lot, corps fourni"         OK      verdict_brief abc123 abc123 40
  t "brief pile à la borne"              OK      verdict_brief abc123 abc123 5
  t "brief réduit à un titre"            FAIL    verdict_brief abc123 abc123 2
  t "brief du lot PRÉCÉDENT"             FAIL    verdict_brief vieux1 abc123 40
  t "aucun brief"                        INCONNU verdict_brief "" abc123 40
  t "compte de lignes illisible"         INCONNU verdict_brief abc123 abc123 ""
  t "zéro erreur"                        OK      verdict_compte 0 0
  t "erreurs présentes"                  FAIL    verdict_compte 3 0
  t "compte non mesuré"                  INCONNU verdict_compte "" 0
  t "piège du grep -c || echo 0"         INCONNU verdict_compte "0 0" 0
  t "compte non numérique"               INCONNU verdict_compte "abc" 0
  t "clone à jour"                       OK      verdict_clone 0 non
  t "retard sans apport (post-squash)"    OK      verdict_clone 2 oui
  t "retard avec apport manquant"        FAIL    verdict_clone 2 non
  t "retard non mesuré"                  INCONNU verdict_clone "" oui
  t "retard non numérique"               INCONNU verdict_clone "abc" oui
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
  #  Le 4ᵉ argument est le seuil ; 40 min = 2 ticks de 15 min manqués, comme C15.
  t "silence, producteur vivant"         OK      verdict_alerte "" "" 5 40
  t "échec sans aucune alerte"           FAIL    verdict_alerte "" 30 5 40
  t "alerte postérieure à l'échec"       OK      verdict_alerte 25 30 5 40
  t "alerte dans le cooldown d'1 h"      OK      verdict_alerte 80 30 5 40
  t "échec ancien jamais alerté"         FAIL    verdict_alerte 5000 30 5 40
  #  ── #306 : le silence d'un producteur mort n'est pas un silence normal ─────
  #  Le cas vécu le 11/08/2026 : check-reliability mort depuis 135 min sur
  #  l'actif, aucun FAIL au journal — le point répondait OK.
  t "silence, producteur mort (vécu)"    INCONNU verdict_alerte "" "" 135 40
  t "silence, producteur pile au seuil"  OK      verdict_alerte "" "" 40 40
  t "silence, producteur jamais vu"      INCONNU verdict_alerte "" "" "" 40
  t "silence, âge producteur illisible"  INCONNU verdict_alerte "" "" "x" 40
  t "silence, seuil non fourni"          INCONNU verdict_alerte "" "" 5 ""
  t "silence, seuil illisible"           INCONNU verdict_alerte "" "" 5 "x"
  #  Un échec DÉJÀ ÉCRIT prouve que le producteur a tourné : la vivacité ne doit
  #  pas rendre INCONNU un canal démontré muet, sinon on perd l'information.
  t "échec muet malgré producteur mort"  FAIL    verdict_alerte "" 30 999 40
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
