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

#  ⚠️ La liste des fichiers est le CONTRÔLE lui-même : si elle est vide parce que
#  la commande a échoué, on rendrait un vert sans rien avoir examiné. C'est
#  arrivé à la première exécution en CI — `origin/main...HEAD: no merge base`,
#  faute d'un historique assez profond, diff vide, contrôle « réussi ».
#  Une sortie vide n'est PAS un vert (socle 04 §1) : ici, elle est INCONNUE.
#  Comparaison à deux points, qui n'exige aucune base de fusion.
#  ⚠️ Comparaison à l'ARBRE DE TRAVAIL, pas à HEAD. `git diff "$BASE" HEAD` ne
#  liste que les fichiers du dernier COMMIT, alors que la taille est lue sur le
#  disque juste après (`wc -l < "$f"`). Mélanger les deux crée un angle mort :
#  un fichier modifié mais pas encore committé n'apparaît pas dans la liste,
#  donc n'est jamais mesuré — et le contrôle annonce « aucun fichier n'a grossi »
#  en n'ayant pas regardé celui qui venait de grossir.
#
#  Vécu le 08/08/2026 : lancé avant `git commit`, ce contrôle a rendu vert trois
#  fois de suite pendant que la CI, elle, échouait sur `email.py` (656 → 663).
#  J'ai annoncé une CI verte sur la foi de ce vert-là. En intégration continue
#  l'arbre est propre, donc les deux formes sont équivalentes ; en local, seule
#  celle-ci mesure ce qu'on s'apprête à pousser.
if ! CHANGES=$(git diff --name-only "$BASE" 2>&1); then
  echo "::error::Modularité INCONNUE — impossible de comparer à $BASE : $CHANGES"
  echo "Le contrôle n'a rien pu examiner ; ne pas lire ceci comme un succès."
  exit 2
fi
if ! git rev-parse --verify -q "$BASE" >/dev/null; then
  echo "::error::Modularité INCONNUE — la référence $BASE est introuvable."
  exit 2
fi

#  Un fichier DÉPLACÉ n'est pas un fichier neuf.
#
#  Sans détection de renommage, `git show "$BASE:$f"` ne trouve rien au nouveau
#  chemin et le fichier compte pour 0 ligne « avant » : ranger un script de 693
#  lignes le fait alors apparaître comme une création au-dessus du plafond. Le
#  rangement, qui ne change pas une seule ligne de code, devient une violation de
#  la règle de modularité — et la seule issue serait de désarmer le contrôle.
#  Vécu le 15/08/2026 en rangeant l'outillage du poste (#337).
RENOMMAGES=$(git diff -M --name-status "$BASE" 2>/dev/null | awk '$1 ~ /^R/ {print $3"	"$2}') || RENOMMAGES=""

#  Chemin qu'occupait $1 dans $BASE, ou rien si le fichier est réellement neuf.
chemin_origine() {
  printf '%s
' "$RENOMMAGES" | awk -F'	' -v n="$1" '$1 == n { print $2; exit }'
}

fautifs=""
while IFS= read -r f; do
  case "$f" in
    *.py|*.ts|*.js|*.mjs|*.svelte|*.sh) ;;
    *) continue ;;
  esac
  [ -f "$f" ] || continue                       # supprimé
  ap=$(wc -l < "$f")
  av=$(git show "$BASE:$f" 2>/dev/null | wc -l) || av=0
  if [ "${av:-0}" -eq 0 ]; then                 # absent au nouveau chemin : déplacé ?
    origine=$(chemin_origine "$f")
    [ -n "$origine" ] && av=$(git show "$BASE:$origine" 2>/dev/null | wc -l)
  fi
  case "$(verdict "${av:-0}" "$ap")" in
    grossit)        fautifs="$fautifs  $f : $av → $ap lignes (déjà au-dessus de $PLAFOND, et il grossit)\n" ;;
    neuf-trop-gros) fautifs="$fautifs  $f : $ap lignes pour un fichier NEUF (plafond $PLAFOND)\n" ;;
  esac
done <<< "$CHANGES"

if [ -n "$fautifs" ]; then
  printf "::error::Modularité (rang 1) — découper avant d'ajouter :\n"
  printf "%b" "$fautifs"
  printf "\nLa règle est « au fil de l'eau » : on découpe le fichier QUAND on y touche.\n"
  exit 1
fi
echo "✓ Modularité : aucun fichier de plus de $PLAFOND lignes n'a grossi."
