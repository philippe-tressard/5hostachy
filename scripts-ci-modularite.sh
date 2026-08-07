#!/usr/bin/env bash
# =============================================================================
#  Modularité (rang 1) — un fichier de plus de 500 lignes ne doit pas GROSSIR.
#
#  POURQUOI ce contrôle et pas un simple plafond : le dépôt compte 26 fichiers
#  déjà au-dessus de 500 lignes. Un plafond absolu échouerait en permanence,
#  donc serait désactivé dans la semaine. La règle du socle est « l'existant se
#  découpe AU FIL DE L'EAU » : ce qui est interdit, ce n'est pas d'être gros,
#  c'est de **grossir** sans découper.
#
#  Trois verdicts :
#    - fichier NEUF > 500 lignes            → échec (règle « nouvelle fonctionnalité »)
#    - fichier déjà > 500 qui GROSSIT       → échec (dérogation au fil de l'eau)
#    - fichier déjà > 500 qui MAIGRIT       → OK, c'est le progrès attendu
#
#  Constaté le 07/08/2026 : flux.py 996 → 1044 et check-reliability.sh 486 → 565,
#  sur trois lots successifs, sans qu'aucun contrôle ne le signale.
#
#  Usage : bash scripts-ci-modularite.sh [base]     (défaut : origin/main)
#          bash scripts-ci-modularite.sh --selftest
# =============================================================================
set -uo pipefail
PLAFOND=500

verdict() {  # $1 = lignes avant (0 = fichier neuf), $2 = lignes après
  local av=$1 ap=$2
  if [ "$av" -eq 0 ]; then
    [ "$ap" -gt "$PLAFOND" ] && echo neuf-trop-gros || echo ok
  elif [ "$ap" -le "$PLAFOND" ]; then
    echo ok
  elif [ "$ap" -gt "$av" ]; then
    echo grossit
  else
    echo ok
  fi
}

if [ "${1:-}" = "--selftest" ]; then
  st=0
  t() { r=$(verdict "$2" "$3"); [ "$r" = "$4" ] && echo "PASS  $1 → $r" \
        || { echo "FAIL  $1  attendu=$4 obtenu=$r"; st=1; }; }
  t "fichier neuf court"                    0   120 ok
  t "fichier neuf trop gros"                0   501 neuf-trop-gros
  t "fichier neuf pile au plafond"          0   500 ok
  t "petit fichier qui grossit sous plafond" 100 480 ok
  t "petit fichier qui franchit le plafond" 486 565 grossit
  t "gros fichier qui grossit"              996 1044 grossit
  t "gros fichier qui maigrit"              737 684 ok
  t "gros fichier inchangé"                 880 880 ok
  t "gros fichier qui repasse sous le plafond" 520 400 ok
  [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $st
fi

BASE="${1:-origin/main}"
fautifs=""
while IFS= read -r f; do
  case "$f" in
    *.py|*.ts|*.js|*.mjs|*.svelte|*.sh) ;;
    *) continue ;;
  esac
  [ -f "$f" ] || continue                       # supprimé
  ap=$(wc -l < "$f")
  av=$(git show "$BASE:$f" 2>/dev/null | wc -l) || av=0
  case "$(verdict "${av:-0}" "$ap")" in
    grossit)        fautifs="$fautifs  $f : $av → $ap lignes (déjà au-dessus de $PLAFOND, et il grossit)\n" ;;
    neuf-trop-gros) fautifs="$fautifs  $f : $ap lignes pour un fichier NEUF (plafond $PLAFOND)\n" ;;
  esac
done < <(git diff --name-only "$BASE"...HEAD)

if [ -n "$fautifs" ]; then
  printf "::error::Modularité (rang 1) — découper avant d'ajouter :\n"
  printf "%b" "$fautifs"
  printf "\nLa règle est « au fil de l'eau » : on découpe le fichier QUAND on y touche.\n"
  exit 1
fi
echo "✓ Modularité : aucun fichier de plus de $PLAFOND lignes n'a grossi."
