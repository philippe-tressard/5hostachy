#!/usr/bin/env bash
# =============================================================================
#  Modularité (rang 1) — AUCUN fichier au-dessus de son plafond.
#
#  🔴 PLAFOND ABSOLU depuis le 02/10/2026 (#779). Jusque-là, ce contrôle ne
#  refusait qu'un fichier NEUF trop long ou un fichier déjà trop long qui
#  GROSSISSAIT : le dépôt en comptait 26 au départ (07/08/2026), un plafond
#  absolu aurait échoué en permanence et aurait été désarmé dans la semaine. La
#  règle était donc « l'existant se découpe au fil de l'eau », et le ticket #779
#  en tenait la carte.
#
#  La carte est VIDE depuis la v2.91.1 : plus un seul fichier au-dessus de son
#  plafond. La tolérance n'a plus rien à tolérer — et la garder laisserait la
#  carte se remplir de nouveau sans un mot : un fichier à 480 lignes qui passait
#  à 520 par un simple reformatage était accepté (« volume inchangé »), et ne
#  repassait plus jamais sous la barre puisque seule sa CROISSANCE était jugée.
#
#  Ce que la version précédente savait, et qui ne sert plus :
#    - la mesure en VOLUME (caractères hors blancs, #419) distinguait un
#      reformatage d'un ajout, le jour où Prettier a été posé sur un front dont
#      treize fichiers dépassaient. Prettier et Ruff sont désormais imposés en CI
#      (`prettier --check`, `ruff format --check`) : un formatage ne peut plus
#      ajouter de lignes en douce. Une montée de version qui ferait déborder un
#      fichier est un vrai débordement, et il se découpe ;
#    - la comparaison à une base git, et la détection des renommages qui allait
#      avec : un plafond absolu juge l'arbre tel qu'il est, d'où qu'il vienne.
#
#  Deux plafonds, selon la NATURE du fichier (`plafond_de`) :
#    - le code (.py .ts .js .mjs .svelte .sh) : 500 lignes, la règle du socle ;
#    - les feuilles de style (.css) : 1 500 (#499, 19/08/2026). Les feuilles
#      partagées sont le SEUL endroit où un style se met en commun : chaque
#      extraction de composant y pousse du contenu. Les mesurer à 500 ferait de
#      chaque factorisation réussie une violation.
#
#  Usage : bash scripts-ci-modularite.sh
#          bash scripts-ci-modularite.sh --selftest
# =============================================================================
set -uo pipefail
PLAFOND=500
PLAFOND_STYLE=1500

#  Plafond d'un chemin selon sa nature ; RIEN pour une extension hors règle —
#  et la sortie le dit (« NON MESURÉ ») plutôt que de laisser croire à
#  l'exhaustivité (`standards/04`).
plafond_de() {
  case "$1" in
    *.py|*.ts|*.js|*.mjs|*.svelte|*.sh) echo "$PLAFOND" ;;
    *.css)                              echo "$PLAFOND_STYLE" ;;
  esac
}

#  Lit des lignes « <lignes> <chemin> » (la sortie de `wc -l`) et rend celles
#  qui dépassent le plafond de leur nature. Fonction PURE : c'est elle que
#  l'auto-test exerce, sans dépôt ni fichier.
hors_plafond() {
  local n f p
  while read -r n f; do
    [ "$f" = "total" ] && continue        # ligne de cumul de `wc`
    p=$(plafond_de "$f")
    [ -n "$p" ] || continue
    [ "$n" -gt "$p" ] && echo "  $f : $n lignes (plafond $p)"
  done
  return 0
}

if [ "${1:-}" = "--selftest" ]; then
  st=0
  t() { r=$(printf '%s\n' "$2" | hors_plafond); [ "$r" = "$3" ] && echo "PASS  $1" \
        || { echo "FAIL  $1  attendu=[$3] obtenu=[$r]"; st=1; }; }
  t "code pile au plafond"            "500 api/app/a.py"         ""
  t "code un cran au-dessus"          "501 api/app/a.py"         "  api/app/a.py : 501 lignes (plafond 500)"
  t "composant Svelte au-dessus"      "730 front/x/+page.svelte" "  front/x/+page.svelte : 730 lignes (plafond 500)"
  t "script shell au-dessus"          "565 scripts/c.sh"         "  scripts/c.sh : 565 lignes (plafond 500)"
  #  #499 — les styles ont LEUR plafond : 1 160 lignes passent, pas 1 501.
  t "feuille de style sous le sien"   "1160 front/src/app.css"   ""
  t "feuille de style au-dessus"      "1501 front/src/app.css"   "  front/src/app.css : 1501 lignes (plafond 1500)"
  t "extension hors règle ignorée"    "9000 docs/manuel.html"    ""
  t "ligne de cumul de wc ignorée"    "99999 total"              ""
  #  Un chemin à espace reste entier : `read` lui laisse tout le reste de la ligne.
  t "chemin avec une espace"          "600 front/a b.ts"         "  front/a b.ts : 600 lignes (plafond 500)"
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st
fi

#  ⚠️ L'ARBRE DE TRAVAIL, fichiers non suivis compris (hors .gitignore) : en
#  local, ce contrôle doit mesurer ce qu'on s'apprête à committer — un fichier
#  neuf pas encore ajouté resterait sinon invisible. Vécu le 08/08/2026 : un
#  contrôle qui ne lisait que les commits a rendu vert trois fois pendant que la
#  CI échouait.
#  Un seul `wc` pour tous les fichiers : un sous-processus par fichier prenait
#  plus de deux minutes sous Windows. Les extensions filtrées ici sont celles de
#  `plafond_de` ; une extension qu'il ignore serait de toute façon écartée par
#  `hors_plafond`, donc les deux listes ne peuvent pas se contredire.
if ! LISTE=$(git ls-files -z --cached --others --exclude-standard 2>&1 | tr '\0' '\n'); then
  echo "::error::Modularité INCONNUE — git ls-files a échoué : $LISTE"
  exit 2
fi
MESURES=$(printf '%s\n' "$LISTE" | grep -E '\.(py|ts|js|mjs|svelte|sh|css)$' \
  | while IFS= read -r f; do [ -f "$f" ] && printf '%s\0' "$f"; done \
  | xargs -0 wc -l | grep -v ' total$')

#  🔴 CAS ZÉRO : une liste vide n'est pas un vert, c'est un contrôle qui n'a
#  rien regardé (`standards/04` §2). Le dépôt compte des centaines de fichiers
#  de code : en mesurer moins de cent, c'est que la lecture a échoué.
nb=$(printf '%s\n' "$MESURES" | grep -c .)
if [ "$nb" -lt 100 ]; then
  echo "::error::Modularité INCONNUE — seulement $nb fichier(s) mesuré(s) : la liste est tronquée."
  exit 2
fi

fautifs=$(printf '%s\n' "$MESURES" | hors_plafond)
if [ -n "$fautifs" ]; then
  printf "::error::Modularité (rang 1) — fichier(s) au-dessus de leur plafond :\n%s\n" "$fautifs"
  printf "\nDécouper — et factoriser d'abord s'il y a de la copie : scinder un fichier\n"
  printf "plein de doublons ne fait que les répartir (standards/02 §6).\n"
  exit 1
fi
echo "✓ Modularité : $nb fichiers mesurés, aucun au-dessus de son plafond (code $PLAFOND l. · styles $PLAFOND_STYLE l.)."
echo "  NON MESURÉ, faute de règle : .html .md .json .yml .sql, et toute autre extension."
