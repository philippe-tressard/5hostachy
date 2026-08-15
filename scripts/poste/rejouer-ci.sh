#!/usr/bin/env bash
# =============================================================================
#  rejouer-ci.sh — Rejoue en local, sur le poste, les commandes de la CI.
#
#  POURQUOI (#319). Le 12/08/2026, la CI est passée rouge sur `Lint Python
#  (Ruff)` après un lot où pytest, svelte-check, le build, les six lints du front
#  et les self-tests des scripts avaient tous été rejoués à la main. **Le seul
#  job non lancé est le seul qui a échoué.** La skill `avant-commit` §7 demande
#  pourtant d'exécuter chaque commande de chaque job, et donne même le `grep`
#  pour les extraire. Rien ne forçait à le faire, rien ne constatait qu'on
#  l'avait fait.
#
#  Le point 0c du pré-check regarde la CI DISTANTE et PASSÉE. Entre les deux, il
#  y a tout le lot qu'on s'apprête à pousser. Ce script comble cet intervalle ;
#  le point 16 du pré-check lit sa trace.
#
#  CE QUI FAIT SA VALEUR : il n'a pas de liste. Les commandes sont extraites de
#  `.github/workflows/ci.yml` par `lib-ci-replay.sh`. Une liste recopiée
#  divergerait au premier job ajouté — et c'est le job ajouté qu'on oublie.
#
#  RÈGLES (socle 04) :
#   - une étape non rejouable ici rend INCONNU, jamais OK ;
#   - une étape d'INSTALLATION n'est pas un contrôle : elle est affichée comme
#     telle, et non exécutée — elle écraserait l'environnement du poste ;
#   - le compte de ce qui a été vérifié est affiché : « 0 étape rejouée » n'est
#     pas un succès, c'est un parseur qui n'a rien compris ;
#   - la parité entre les `run:` écrits et les étapes extraites est vérifiée
#     AVANT tout : sans elle, le script rendrait un vert sur ce qu'il n'a pas lu.
#
#  Usage : bash scripts/poste/rejouer-ci.sh                 # tous les jobs, écrit la trace
#          bash scripts/poste/rejouer-ci.sh lint-backend …  # un ou plusieurs jobs, sans trace
#          bash scripts/poste/rejouer-ci.sh --selftest      # éprouve l'extraction
# =============================================================================
set -uo pipefail

CI="${CI_FICHIER:-.github/workflows/ci.yml}"
MARQUEUR="${MARQUEUR_CI:-.git/rejeu-ci.ok}"

# shellcheck source=lib-ci-replay.sh
#  Modules à la racine du dépôt — cf. le commentaire de precheck-mep.sh (#337).
RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RACINE_DEPOT" || exit 1   # le rejeu extrait .github/workflows/ci.yml en relatif
. "$RACINE_DEPOT/lib-ci-replay.sh"

if [ "${1:-}" = "--selftest" ]; then
  ci_replay_selftest
  exit $?
fi

RACINE=$(git rev-parse --show-toplevel 2>/dev/null) || RACINE=$(pwd)
cd "$RACINE" || exit 2
[ -f "$CI" ] || { echo "✗ $CI introuvable — lancer depuis la racine du dépôt."; exit 2; }

#  En intégration continue, `pip install` dépose ses exécutables dans un
#  répertoire déjà présent dans le PATH. Sur un poste Windows, non : `ruff` et
#  `pytest` sont installés et introuvables depuis Git Bash. Sans cette ligne, le
#  job qui a motivé #319 resterait INCONNU pour toujours — c'est-à-dire jamais
#  rejoué, ce que ce script existe précisément pour empêcher.
#  Le chemin est DEMANDÉ à Python, jamais écrit en dur : il dépend de la version
#  installée et changerait au prochain interpréteur.
SCRIPTS_PY=$(python -c "import sysconfig; print(sysconfig.get_path('scripts'))" 2>/dev/null)
[ -n "$SCRIPTS_PY" ] && [ -d "$SCRIPTS_PY" ] && PATH="$SCRIPTS_PY:$PATH" && export PATH

FILTRE="$*"
SHA=$(git rev-parse HEAD 2>/dev/null)
SHA_COURT=$(git rev-parse --short HEAD 2>/dev/null)

# ── Parité : refuser de conclure sur ce qu'on n'a pas lu ─────────────────────
read -r ECRIT EXTRAIT <<< "$(ci_parite "$CI")"
if [ "${ECRIT:-0}" -eq 0 ] || [ "$ECRIT" != "$EXTRAIT" ]; then
  echo "✗ Extraction INCOMPLÈTE — $ECRIT commande(s) \`run:\` écrite(s), $EXTRAIT extraite(s)."
  echo "  Le fichier a changé de forme : corriger \`ci_extraire\` dans lib-ci-replay.sh."
  echo "  Ne pas lire ceci comme un succès — rien n'a été rejoué."
  exit 2
fi

TMP=$(mktemp -d) || exit 2
trap 'rm -rf "$TMP"' EXIT
ci_extraire < "$CI" > "$TMP/flux"

NB_OK=0; NB_FAIL=0; NB_INCONNU=0; NB_PREP=0

#  Le verdict et le job sont en TÊTE, le nom de l'étape en queue : `printf`
#  compte des OCTETS, pas des caractères, si bien qu'une colonne de largeur fixe
#  contenant « Modularité » ou « Libellés » se décale d'autant d'accents. Une
#  colonne qui ne s'aligne pas se lit mal, et un rapport qu'on lit mal, on cesse
#  de le lire.
rapporter() {              # $1 = verdict, $2 = job, $3 = étape, $4 = détail
  local icone
  case "$1" in
    OK)      icone="✓"; NB_OK=$((NB_OK+1)) ;;
    FAIL)    icone="✗"; NB_FAIL=$((NB_FAIL+1)) ;;
    INCONNU) icone="?"; NB_INCONNU=$((NB_INCONNU+1)) ;;
    PRÉP)    icone="·"; NB_PREP=$((NB_PREP+1)) ;;
    *)       icone="·" ;;
  esac
  printf "%s %-7s %-15s %s%s\n" "$icone" "$1" "$2" "$3" "${4:+  — $4}"
}

version_locale() {         # $1 = uses — ce que la CI ÉPINGLE, ce que le poste a
  case "$1" in
    *setup-python*) python --version 2>&1 | awk '{print $2}' ;;
    *setup-node*)   node --version 2>&1 | tr -d 'v' ;;
    *) echo "" ;;
  esac
}

executer() {               # $1 = job, $2 = étape, $3 = rép, corps dans $TMP/corps
  local corps genre sortie code duree t0
  corps=$(ci_substituer "$SHA_COURT" < "$TMP/corps")
  genre=$(printf '%s\n' "$corps" | ci_classer)

  case "$genre" in
    PREPARATION)
      rapporter "PRÉP" "$1" "$2" "installation — non exécutée sur le poste"
      return ;;
    INCONNU*)
      rapporter INCONNU "$1" "$2" "${genre#INCONNU }"
      return ;;
  esac

  printf '%s\n' "$corps" > "$TMP/etape.sh"
  t0=$(date +%s)
  (
    cd "$RACINE${3:+/$3}" || exit 127
    while IFS= read -r kv; do
      [ -z "$kv" ] && continue
      local_cle=${kv%%:*}
      local_val=${kv#*: }
      local_val=${local_val%\"}; local_val=${local_val#\"}
      local_val=${local_val%\'}; local_val=${local_val#\'}
      export "$local_cle=$local_val"
    done < "$TMP/env"
    bash -e "$TMP/etape.sh" < /dev/null
  ) > "$TMP/sortie" 2>&1
  code=$?
  duree=$(( $(date +%s) - t0 ))

  sortie=$(ci_requalifier "$code" < "$TMP/sortie")
  case "$sortie" in
    OK)       rapporter OK "$1" "$2" "${duree}s" ;;
    INCONNU*) rapporter INCONNU "$1" "$2" "${sortie#INCONNU } (${duree}s)" ;;
    *)        rapporter FAIL "$1" "$2" "code $code (${duree}s)"
              sed 's/^/      │ /' "$TMP/sortie" | tail -15 ;;
  esac
}

# ── Déroulement ──────────────────────────────────────────────────────────────
echo "Rejeu de $CI sur $SHA_COURT — $ECRIT commande(s) extraite(s)"
[ -n "$FILTRE" ] && echo "Jobs retenus : $FILTRE"
echo "───────────────────────────────────────────────────────────────────────────────"

JOB=""; ETAPE=""; GENRE=""; REP=""; USES=""; WITH=""; DANS_RUN=0; RETENU=1
: > "$TMP/env"; : > "$TMP/corps"

lancer_si_besoin() {
  [ "$RETENU" -eq 1 ] || return
  [ "$GENRE" = "run" ] || return
  executer "$JOB" "$ETAPE" "$REP"
}

while IFS= read -r ligne <&3; do
  case "$ligne" in
    '@@ERREUR'*)
      echo "✗ Protocole rompu : ${ligne#*$'\t'}"
      echo "  Rien n'a été rejoué — ne pas lire ceci comme un succès."
      exit 2 ;;
    '@@STEP'*)
      IFS=$'\t' read -r _ JOB _ ETAPE GENRE REP USES WITH <<< "$ligne"
      #  `-` est le marqueur de champ vide posé par `nz()` côté extraction.
      [ "$ETAPE" = "-" ] && ETAPE=""
      [ "$REP"   = "-" ] && REP=""
      [ "$USES"  = "-" ] && USES=""
      [ "$WITH"  = "-" ] && WITH=""
      : > "$TMP/env"; : > "$TMP/corps"; DANS_RUN=0
      RETENU=1
      if [ -n "$FILTRE" ]; then
        case " $FILTRE " in *" $JOB "*) RETENU=1 ;; *) RETENU=0 ;; esac
      fi
      if [ "$GENRE" = "uses" ] && [ "$RETENU" -eq 1 ]; then
        case "$USES" in
          *checkout*) ;;
          *) rapporter "ENV" "$JOB" "${ETAPE:-$USES}" \
               "épinglé « ${WITH:-—} » · poste $(version_locale "$USES")" ;;
        esac
      fi ;;
    '@@ENV'*)   printf '%s\n' "${ligne#*$'\t'}" >> "$TMP/env" ;;
    '@@RUN')    DANS_RUN=1; : > "$TMP/corps" ;;
    '@@END')    DANS_RUN=0; lancer_si_besoin ;;
    *)          [ "$DANS_RUN" -eq 1 ] && printf '%s\n' "$ligne" >> "$TMP/corps" ;;
  esac
done 3< "$TMP/flux"

# ── Conclusion ───────────────────────────────────────────────────────────────
REJOUEES=$((NB_OK + NB_FAIL + NB_INCONNU))
echo "───────────────────────────────────────────────────────────────────────────────"
printf "%d étape(s) rejouée(s) sur %d extraite(s) — OK=%d ÉCHEC=%d INCONNU=%d (préparation=%d)\n" \
       "$REJOUEES" "$ECRIT" "$NB_OK" "$NB_FAIL" "$NB_INCONNU" "$NB_PREP"

if [ "$REJOUEES" -eq 0 ]; then
  echo "? Aucune étape rejouée — ce n'est pas un succès, c'est une absence de mesure."
  exit 2
fi

if [ -n "$FILTRE" ]; then
  echo "  (rejeu partiel : aucune trace écrite — le point 16 du pré-check exige le rejeu complet.)"
else
  mkdir -p "$(dirname "$MARQUEUR")"
  printf '%s %s OK=%d FAIL=%d INCONNU=%d\n' "$SHA" "$(date +%s)" "$NB_OK" "$NB_FAIL" "$NB_INCONNU" > "$MARQUEUR"
fi

[ "$NB_FAIL" -gt 0 ] && { echo "✗ La CI échouerait — corriger avant de pousser."; exit 1; }
[ "$NB_INCONNU" -gt 0 ] && { echo "? Des étapes n'ont pas pu être rejouées ici : un INCONNU n'est pas un vert."; exit 2; }
echo "✓ Toutes les étapes rejouables sont passées."
exit 0
