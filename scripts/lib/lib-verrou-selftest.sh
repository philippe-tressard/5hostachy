#!/usr/bin/env bash
# =============================================================================
#  lib-verrou-selftest.sh — les épreuves du VERROU de bascule
#
#  Extrait de `lib-verdicts-selftest.sh` le 12/09/2026, au fil de l'eau : ce
#  fichier a franchi son plafond de modularité en les recevant. La coupe suit la
#  NATURE de l'objet — tout ce qui éprouve le verrou de bascule — et non le
#  numéro des contrôles ; même geste que `sudo_selftest` (15/08) pour C20/C21.
#
#  Deux fonctions sont éprouvées ici, et elles ne vivent pas au même endroit :
#    `verrou_recent`            — `lib-verrou.sh`, consommée par auto-deploy,
#                                 health-watch et le seuil de C12
#    `verdict_verrou_orphelin`  — `lib-verdicts.sh`, la décision de C12
#
#  ⚠️ Ce module n'est PAS autonome : il emploie `st_fail`, défini par son
#  appelant `verdicts_selftest`, et les deux fonctions ci-dessus. Le sourcer seul
#  ne produirait rien.
# =============================================================================

verrou_selftest() {
    echo "-- verrou_recent (auto-deploy · health-watch · C12) --"
    vr() { # description attendu mtime maintenant seuil
      local desc="$1" exp="$2"; shift 2
      local got; got=$(verrou_recent "$@")
      if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
      else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
    }
    vr "verrou de 1 min : opération en cours"   oui 999940 1000000 900
    vr "verrou de 14 min : encore en cours"     oui 999160 1000000 900
    #  🔴 LA BORNE, et c'est elle qui manquait à `auto-deploy` : sans elle, il
    #  attendait INDÉFINIMENT sur un verrou laissé par une bascule tuée — plus
    #  aucun déploiement, en silence (#915). Ce cas échoue sur la version fautive,
    #  qui ne testait que la présence du fichier.
    vr "verrou de 16 min : PÉRIMÉ"              non 999040 1000000 900
    vr "verrou de 3 jours : PÉRIMÉ"             non 740800 1000000 900
    #  ⚠️ Ici l'inconnu S'ABSTIENT, à l'inverse de `bascule_en_cours` : on
    #  déciderait de DÉMARRER des conteneurs. Conclure « périmé » sur une mesure
    #  absente rouvrirait le split-brain du 12/09 par la porte du contrôle.
    vr "horodatage illisible"                   oui "abc" 1000000 900
    vr "horodatage vide"                        oui ""    1000000 900
    vr "horodatage nul"                         oui 0     1000000 900
    #  Horloge recalée en arrière (C11 surveille la dérive) : âge négatif.
    vr "verrou daté du futur"                   oui 1000600 1000000 900

    echo "-- verdict_verrou_orphelin (C12) --"
    vo() { # description attendu dernier maintenant fenetre
      local desc="$1" exp="$2"; shift 2
      local got; got=$(verdict_verrou_orphelin "$@")
      if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
      else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
    }
    #  🔴 Le cas qui donne sa raison d'être au contrôle : une bascule tuée laisse
    #  un verrou que health-watch efface sous 15 min. L'ancien C12 lisait l'âge du
    #  FICHIER — il ne trouvait donc plus rien, et rendait OK. Ici c'est la TRACE
    #  du nettoyage qui parle, et elle reste.
    vo "nettoyage il y a 10 min"        "RECENT:10" 999400 1000000 86400
    vo "nettoyage il y a 23 h"          "RECENT:1380" 917200 1000000 86400
    #  Hors fenêtre : un incident de l'autre semaine ne crie pas tous les 1/4 h.
    vo "nettoyage il y a 8 jours"       OK 308800 1000000 86400
    #  Un vrai vert, et il est MESURÉ : aucun nettoyage n'a jamais été journalisé.
    vo "aucun nettoyage jamais vu"      OK 0 1000000 86400
    #  🔴 LE CAS ZÉRO : journal absent ou illisible. C'est exactement l'erreur que
    #  ce contrôle commettait — rendre OK sans avoir pu regarder (`standards/04` §2).
    vo "journal absent"                 INCONNU "inconnu" 1000000 86400
    vo "journal vide"                   INCONNU "" 1000000 86400
    vo "horodatage du futur"            INCONNU 1000600 1000000 86400


    echo "-- verdict_ordre_bascule (C26) --"
    vo2() { # description attendu journal
      local desc="$1" exp="$2" journal="$3"
      local got; got=$(printf '%s' "$journal" | verdict_ordre_bascule)
      if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
      else echo "FAIL  $desc  attendu=$exp obtenu=$got"; st_fail=1; fi
    }
    #  L'ordre CORRECT : la pose précède l'arrêt des conteneurs du peer.
    vo2 "pose puis action" OK \
      '===== Bascule rpi1 → rpi2 =====
[0/7] Pre-flight...
  → Lock bascule posé sur les DEUX nœuds
  ⚠ Peer a 4 conteneur(s) actif(s) — arrêt avant bascule.
[1/7] Sync uploads...'
    #  🔴 L'ORDRE FAUTIF, celui d'avant le 12/09/2026 : les conteneurs du peer
    #  étaient arrêtés AVANT la pose, et `auto-deploy` pouvait passer entre les
    #  deux. Ce cas est la raison d'être du contrôle.
    vo2 "action puis pose : TARDIF" TARDIF \
      '===== Bascule rpi1 → rpi2 =====
  ⚠ Peer a 4 conteneur(s) actif(s) — arrêt avant bascule.
  → Lock bascule posé sur le peer.
[1/7] Sync uploads...'
    #  L'ancienne formulation (avant #916) doit rester reconnue : sinon le
    #  contrôle rendrait INCONNU sur tout l'historique, et on l'ignorerait.
    vo2 "formulation d'avant #916" OK \
      '  → Lock bascule posé sur le peer.
[1/7] Sync uploads...'
    #  Une bascule arrêtée avant toute action : rien à reprocher.
    vo2 "pose seule, pas d'action" OK '  → Lock bascule posé sur le peer.'
    #  🔴 LE CAS ZÉRO : journal tronqué par la rotation, ou bascule qui n'a pas
    #  posé. On ne sait pas — et c'est le cas le PLUS probable en production.
    vo2 "aucune pose relevée" INCONNU '[0/7] Pre-flight...
[1/7] Sync uploads...'
    vo2 "journal vide" INCONNU ''

  return ${st_fail:-0}
}
