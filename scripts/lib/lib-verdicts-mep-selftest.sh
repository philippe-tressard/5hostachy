#!/usr/bin/env bash
# =============================================================================
#  Auto-tests des verdicts du PRÉ-CHECK MEP — extrait de `lib-verdicts-mep.sh`
#  le 20/08/2026, au fil de l'eau.
#
#  POURQUOI. Le garde-fou de modularité a refusé les lignes qu'ajoutait le point
#  18 (parité des IMAGES du standby, #511) : `lib-verdicts-mep.sh` passait de 491
#  à 523 lignes. La règle est « on découpe QUAND on y touche ».
#
#  La coupe reprend celle de `lib-verdicts.sh` → `lib-verdicts-selftest.sh`
#  (19/08/2026), et pour la même raison : d'un côté les fonctions PURES que le
#  pré-check appelle, de l'autre ce qui les éprouve. Les deux n'ont pas la même
#  raison de changer — et la seconde grossit à chaque incident, la première non.
#
#  ⚠️ Ce fichier a besoin de `lib-verdicts-mep.sh` : il est sourcé APRÈS lui,
#  jamais seul. `precheck-mep.sh --selftest` s'en charge.
# =============================================================================


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
  #  0c — un échec que le lot corrige ne bloque pas son propre push (#318).
  eb() {  # $1 = libellé, $2 = attendu, $3 = liste sha:ancêtre
    local got; got=$(echecs_bloquants "$3")
    if [ "$got" = "$2" ]; then echo "PASS  $1 → '$got'"
    else echo "FAIL  $1  attendu='$2' obtenu='$got'"; st=1; fi
  }
  eb "aucun échec"                        "0" ""
  eb "que des succès"                     "0" "success:b8aeb1e:non success:28b1e9f:non"
  #  (2) Le cas du 12/08 au matin : le correctif est commité, rien n a encore
  #  tourné après l échec, mais HEAD descend du commit fautif.
  eb "échec dépassé par HEAD"             "0" "failure:b003e0d:oui"
  #  (1) Le cas du 12/08 à midi : le squash a détruit l ascendance, mais des
  #  runs plus récents ont réussi. Sans cette règle, 0c bloquerait pour toujours.
  eb "échec suivi d un succès (squash)"   "0" "success:b8aeb1e:non failure:b003e0d:non"
  eb "échec sur un commit étranger"       "1 9f1c2ab" "failure:9f1c2ab:non"
  eb "le plus récent a échoué"            "1 9f1c2ab" "failure:9f1c2ab:non success:aaa1111:non"
  eb "deux échecs, un seul dépassé"       "1 9f1c2ab" "failure:9f1c2ab:non failure:b003e0d:oui"
  #  Ascendance non mesurable (sha absent du clone) : on ne conclut pas au vert.
  eb "ascendance inconnue"                "1 deadbee" "failure:deadbee:?"
  #  Un run annulé ou en cours n est ni un échec ni un succès : il ne doit ni
  #  bloquer, ni servir à déclarer un échec dépassé.
  eb "run annulé ignoré"                  "1 9f1c2ab" "cancelled:ccc3333:non failure:9f1c2ab:non"
  t "clone à jour"                       OK      verdict_clone 0 non
  t "retard sans apport (post-squash)"    OK      verdict_clone 2 oui
  t "retard avec apport manquant"        FAIL    verdict_clone 2 non
  t "retard non mesuré"                  INCONNU verdict_clone "" oui
  t "retard non numérique"               INCONNU verdict_clone "abc" oui
  t "HEAD identiques"                    OK      verdict_parite abc123 abc123
  t "standby en retard : toléré"         ECART   verdict_parite abc123 def456
  #  🔴 #511 — le point 18 : la parité de CODE ci-dessus rend OK là où les
  #  IMAGES sont périmées. Les deux verdicts sont volontairement DISTINCTS, et
  #  ces cas-ci sont ce qui empêche de les refondre « pour simplifier ».
  t "images bâties sur le code du standby" OK      verdict_images_standby abc1234 abc1234
  t "build échoué : images en arrière"     FAIL    verdict_images_standby abc1234 def4567
  t "marqueur absent : rien de prouvé"     INCONNU verdict_images_standby abc1234 ""
  t "code du standby non mesuré"           INCONNU verdict_images_standby "" abc1234
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
  #  ── #319 : la CI rejouée en local couvre-t-elle CE commit ? ───────────────
  t "rejeu complet et vert"              OK      verdict_rejeu_ci abc123 abc123 0 0
  t "rejeu en échec"                     FAIL    verdict_rejeu_ci abc123 abc123 1 0
  #  Une étape non rejouable ici n'est pas un succès : c'est une mesure absente.
  t "rejeu partiellement mesurable"      INCONNU verdict_rejeu_ci abc123 abc123 0 2
  #  Le piège que ce verdict existe pour fermer : une trace vieille d'un lot.
  t "trace d'un autre commit"            INCONNU verdict_rejeu_ci deadbee abc123 0 0
  t "aucune trace"                       INCONNU verdict_rejeu_ci "" abc123 0 0
  t "comptes illisibles"                 INCONNU verdict_rejeu_ci abc123 abc123 "x" 0
  #  ── #502 : l'erreur que CE lot corrige ─────────────────────────────────────
  #  Sans déclaration, rien ne change : le point reste intransigeant.
  t "prod saine, aucune déclaration"     OK      verdict_erreurs_api 0 "" "" abc123 ""
  t "erreurs, aucune déclaration"        FAIL    verdict_erreurs_api 3 "" "" abc123 ""
  t "logs non mesurés"                   INCONNU verdict_erreurs_api "" "" "" abc123 ""
  #  Le cas du 19/08 : les 2 erreurs observées sont celles que ce lot corrige.
  t "toutes les erreurs sont déclarées"  OK      verdict_erreurs_api 2 2 abc123 abc123 "auth/refresh"
  #  Une erreur de PLUS que la signature ne couvre : elle, on ne la connaît pas.
  t "une erreur hors signature"          FAIL    verdict_erreurs_api 3 2 abc123 abc123 "auth/refresh"
  #  🔴 Le cœur du mécanisme : la dérogation ne survit pas à son objet.
  t "signature qui ne sert plus"         FAIL    verdict_erreurs_api 0 0 abc123 abc123 "auth/refresh"
  #  Désarmer le point en le déclarant : refusé, la signature n'ancre rien.
  t "signature vide de littéral"         FAIL    verdict_erreurs_api 2 2 abc123 abc123 ".*"
  t "signature = le niveau de log"       FAIL    verdict_erreurs_api 2 2 abc123 abc123 "ERROR"
  #  Le faux vert par fichier périmé, cousin de celui de 0f.
  t "déclaration d'un autre lot"         FAIL    verdict_erreurs_api 2 2 deadbee abc123 "auth/refresh"
  #  On ne devine pas une déclaration à moitié écrite.
  t "signature sans commit"              INCONNU verdict_erreurs_api 2 2 "" abc123 "auth/refresh"
  t "écartées non mesurées"              INCONNU verdict_erreurs_api 2 "" abc123 abc123 "auth/refresh"
  t "plus d'écartées que d'observées"    INCONNU verdict_erreurs_api 1 2 abc123 abc123 "auth/refresh"
  t "ancrage : chemin"                   oui     signature_ancree "auth/refresh"
  t "ancrage : joker seul"               non     signature_ancree ".*"
  t "ancrage : motif vide"               non     signature_ancree ""
  t "ancrage : mot trop court"           non     signature_ancree "db|io"
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  return $st
}
