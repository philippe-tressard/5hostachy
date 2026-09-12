#!/bin/bash
# =============================================================================
#  lib-export-hors-site.selftest.sh — les CAS D'ESSAI de la copie hors site
#
#  🔴 Sorti de `export-hors-site.sh` le 12/09/2026 : le plafond de modularité
#  (rang 1) a refusé que le script grossisse en recevant le rattrapage borné à
#  la rétention. Il disait vrai — quatre-vingts lignes de cas d'essai n'ont rien
#  à faire dans le fichier qui orchestre le SSH, le disque et le rapport.
#
#  ⚠️ Ce fichier est SOURCÉ, jamais exécuté seul : il s'appuie sur les fonctions
#  que l'appelant a déjà chargées (`lib-export-hors-site.sh`). Le lancer
#  directement ne mesurerait rien — d'où l'absence de bit d'exécution, comme
#  tout module `lib-*.sh`.
#
#  Lancer : bash scripts/poste/export-hors-site.sh --selftest
#
#  Le motif est celui de `lib-analyse-styles.selftest.mjs` côté front : la
#  détection et ses cas d'essai ont deux rythmes différents, donc deux fichiers.
# =============================================================================
  st_fail=0
  check() { # description attendu obtenu
    if [ "$3" = "$2" ]; then echo "PASS  $1  → '$3'"
    else echo "FAIL  $1  attendu='$2' obtenu='$3'"; st_fail=1; fi
  }
  echo "== self-test export-hors-site =="

  check "rpi1 seul répond"          "rpi1"        "$(decider_source 200 000)"
  check "rpi2 seul répond"          "rpi2"        "$(decider_source 000 200)"
  check "les deux répondent"        "split-brain" "$(decider_source 200 200)"
  check "aucun ne répond"           "aucun"       "$(decider_source 000 000)"
  check "503 n'est pas un actif"    "rpi2"        "$(decider_source 503 200)"
  check "codes absents → aucun"     "aucun"       "$(decider_source)"

  # ── Continuité de la série (#775) ──
  # La veille et l'avant-veille présentes, sur une fenêtre de 2 jours : rien ne
  # manque. C'est le cas nominal, et il doit rendre une chaîne VIDE — un
  # contrôle qui crie sur une série complète est désarmé dans la semaine.
  SERIE_OK=$'hostachy_backup_20260904_020000.tar.gz\nhostachy_backup_20260903_020000.tar.gz'
  check "série complète → rien" "" "$(printf '%s' "$SERIE_OK" | jours_manquants 2 20260905)"
  # Un trou au milieu : c'est le seul cas qui compte, et c'est celui qu'une
  # simple présence d'archive ne voit pas.
  SERIE_TROU=$'hostachy_backup_20260904_020000.tar.gz'
  check "un jour manque"    "20260903" "$(printf '%s' "$SERIE_TROU" | jours_manquants 2 20260905)"
  # 🔴 LE CAS ZÉRO : aucune archive du tout. Une liste vide doit rendre TOUS les
  # jours, pas une chaîne vide — sinon « rien à signaler » et « je n'ai rien pu
  # lire » deviennent le même résultat (`standards/04` §1).
  check "liste vide → tous"  "20260904 20260903" "$(printf '' | jours_manquants 2 20260905)"
  # L'archive du jour même n'est pas exigée : elle n'existe qu'après 02:00.
  check "le jour même n'est pas exigé" "" "$(printf '%s' "$SERIE_OK" | jours_manquants 1 20260905)"

  # Le faux négatif du 04/08/2026 : `tar | grep -q` sous pipefail rendait
  # « absent » sur une archive contenant app.db. Le listing est désormais
  # analysé hors de tout tube, et ces cas verrouillent l'analyse.
  LISTING_OK=$'app.db\nuploads/\nuploads/doc.pdf'
  check "app.db en tête de listing"  "oui"        "$(contient_app_db "$LISTING_OK")"
  check "app.db seul"                "oui"        "$(contient_app_db 'app.db')"
  check "listing sans base"          "non"        "$(contient_app_db $'uploads/\nuploads/doc.pdf')"
  check "listing vide"               "non"        "$(contient_app_db '')"
  # Le piège de la sous-chaîne : un fichier nommé app.db DANS uploads n'est pas
  # la base. Une comparaison naïve l'accepterait.
  check "uploads/app.db ne compte pas" "non"      "$(contient_app_db $'uploads/app.db\nuploads/x')"
  check "suffixe app.db2 ne compte pas" "non"     "$(contient_app_db 'app.db2')"

  # ── Liste blanche du nom d'archive ─────────────────────────────────────────
  # Le nom vient du nœud distant et repart dans une commande exécutée là-bas.
  tn() { local r=refuse; nom_valide "$2" && r=ok
         [ "$r" = "$3" ] && echo "PASS  $1" || { echo "FAIL  $1 : attendu=$3 obtenu=$r"; st=1; }; }
  tn "nom d'archive normal"      "hostachy_backup_2026-08-09_030000.tar.gz" ok
  tn "nom vide"                  ""                                          refuse
  tn "chemin absolu"             "/etc/shadow"                               refuse
  tn "remontée de répertoire"    "hostachy_backup_../../etc/shadow.tar.gz"   refuse
  tn "sous-répertoire"           "hostachy_backup_a/b.tar.gz"                refuse
  tn "la base elle-même"         "app.db"                                    refuse
  tn "substitution de commande"  'hostachy_backup_$(id).tar.gz'              refuse

  check "archive saine"             "succes"      "$(verdict_archive 1024 oui oui ok | cut -d'|' -f1)"
  check "archive vide"              "erreur"      "$(verdict_archive 0 oui oui ok | cut -d'|' -f1)"
  check "empreinte différente"      "erreur"      "$(verdict_archive 1024 non oui ok | cut -d'|' -f1)"
  check "app.db absent"             "erreur"      "$(verdict_archive 1024 oui non ok | cut -d'|' -f1)"
  check "base corrompue"            "erreur"      "$(verdict_archive 1024 oui oui 'malformed' | cut -d'|' -f1)"
  # Le cas qui a coûté l'incident du 26/07 ailleurs : l'absence de contrôle
  # lue comme un succès. Ici, ne pas savoir vaut échec.
  check "intégrité non vérifiable"  "erreur"      "$(verdict_archive 1024 oui oui inconnue | cut -d'|' -f1)"

  LISTE=$'a\nb\nc\nd\ne'
  check "rotation garde 3"          $'a\nb'       "$(echo "$LISTE" | archives_a_supprimer 3)"
  check "rotation garde tout"       ""            "$(echo "$LISTE" | archives_a_supprimer 5)"
  check "rotation keep > total"     ""            "$(echo "$LISTE" | archives_a_supprimer 99)"
  # Garde-fou : une config aberrante ne doit pas vider la destination.
  check "keep=0 ne supprime rien"   ""            "$(echo "$LISTE" | archives_a_supprimer 0)"
  check "keep négatif ne fait rien" ""            "$(echo "$LISTE" | archives_a_supprimer -1)"
  check "liste vide"                ""            "$(printf '' | archives_a_supprimer 3)"

  # ── Le rattrapage se borne à la rétention (12/09/2026) ─────────────────────
  # Le cas réel : six archives anciennes sur l'autre nœud, deux conservées. On
  # ne tire QUE celles qui entreraient dans la rétention.
  DIST=$'hostachy_backup_20260908_020000.tar.gz\nhostachy_backup_20260909_020000.tar.gz\nhostachy_backup_20260910_020000.tar.gz'
  LOC=$'hostachy_backup_20260912_020000.tar.gz'
  check "rattrapage borné à 2" "hostachy_backup_20260910_020000.tar.gz" \
        "$(archives_a_rattraper 2 "$LOC" "$DIST")"
  # Rien à tirer quand le local porte déjà les plus récentes.
  check "rien à rattraper" "" \
        "$(archives_a_rattraper 2 $'hostachy_backup_20260911_020000.tar.gz\nhostachy_backup_20260912_020000.tar.gz' "$DIST")"
  # Le distant plus récent que tout le local : les deux partent.
  check "les deux plus récentes viennent du pair" \
        $'hostachy_backup_20260909_020000.tar.gz\nhostachy_backup_20260910_020000.tar.gz' \
        "$(archives_a_rattraper 2 'hostachy_backup_20260101_020000.tar.gz' "$DIST")"
  # Même garde que la rotation : une valeur aberrante ne tire rien.
  check "keep=0 ne tire rien"  "" "$(archives_a_rattraper 0 "$LOC" "$DIST")"
  check "pair vide"            "" "$(archives_a_rattraper 2 "$LOC" '')"

  [ $st_fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st_fail
