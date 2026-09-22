#!/bin/bash
# =============================================================================
#  lib-modules-sources.sh — Un module SOURCÉ ne doit pas pouvoir sortir
#
#  Module sourçable, mais fait pour être lancé : `bash lib-modules-sources.sh
#  --selftest`. Pas de bit x — le job CI « Bits d'exécution versionnés » attend
#  100644 sur les `lib-*.sh`.
#
#  ── POURQUOI CE CONTRÔLE (#1138, 22/09/2026) ────────────────────────────────
#
#  `check-reliability.sh` source ses douze modules dans une boucle, PUIS décide
#  quoi faire de `--selftest`. Un module sourcé hérite des arguments de son
#  appelant : le jour où `lib-env-role.sh` a rejoint cette liste, son propre
#  bloc `if [ "$1" = "--selftest" ]` s'est déclenché, a joué ses cas, et a
#  terminé le script par `exit $?`.
#
#  🔴 Résultat : `check-reliability.sh --selftest` sortait avec **0** sans avoir
#  joué `verdicts_selftest` ni `points_entree_selftest`. Le job CI restait vert
#  en n'éprouvant plus rien — un faux vert dans le contrat du job lui-même, et
#  celui qui l'a introduit ne pouvait pas le voir : la sortie se terminait bien
#  par « tous les cas passent ».
#
#  ⚠️ C'est `standards/04` §27 : un contrôle qui n'annonce que ses fautes ne se
#  fait jamais prendre. C'est en comparant la sortie AVANT et APRÈS le
#  branchement — trois lignes au lieu de trente — que le défaut s'est vu.
#
#  ── LA RÈGLE ────────────────────────────────────────────────────────────────
#
#  Tout module de la boucle `for _mod in …` doit garder son bloc d'exécution
#  derrière « ce fichier est-il EXÉCUTÉ ? », c'est-à-dire :
#
#      if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
#
#  La liste des modules se LIT dans `check-reliability.sh` — recopiée ici, elle
#  divergerait au premier module ajouté, et ce serait précisément celui-là qui
#  échapperait au contrôle.
# =============================================================================

#: Ce qui, au niveau module, met fin au script de l'appelant.
MODULES_SORTIE_MOTIF='^[[:space:]]*(exit|return)[[:space:]]'

# ---------------------------------------------------------------------------
#  modules_sources_liste <chemin de check-reliability.sh>
#
#  Les noms de modules de sa boucle `for _mod in … ; do`. PURE au sens utile :
#  elle ne lit qu'un fichier, et ne décide de rien.
# ---------------------------------------------------------------------------
modules_sources_liste() {
  sed -n 's/^for _mod in \(.*\); do$/\1/p' "$1"
}

# ---------------------------------------------------------------------------
#  verdict_module_gardé <texte du module>
#
#  PURE : reçoit le TEXTE, rend un mot.
#
#    SANS_OBJET  aucun bloc d'exécution : rien à garder
#    OK          le bloc est gardé par un test sur BASH_SOURCE
#    NON_GARDE   il ne regarde que `$1` — il se déclenchera chez l'appelant
# ---------------------------------------------------------------------------
verdict_module_garde() {
  local texte=$1 ligne
  #  Les blocs de tête de fichier (`if [ "${1:-}" = "--selftest" ]`) sont les
  #  seuls concernés : un `exit` à l'intérieur d'une fonction ne s'exécute que
  #  si on appelle la fonction, ce qui est le contrat normal d'un module.
  ligne=$(printf '%s\n' "$texte" | grep -nE '^if .*--selftest' | head -1)
  [ -z "$ligne" ] && { echo SANS_OBJET; return; }
  case "$ligne" in
    *BASH_SOURCE*) echo OK ;;
    *) echo NON_GARDE ;;
  esac
}

_modules_sources_selftest() {
  local echecs=0 obtenu racine liste m fichier
  _c() {
    if [ "$2" = "$3" ]; then echo "  ✓ $1"
    else echo "  ✗ $1 — attendu « $2 », obtenu « $3 »"; echecs=$((echecs + 1)); fi
  }

  echo "lib-modules-sources.sh --selftest"

  #  🔴 LE CAS VÉCU : un bloc qui ne regarde que `$1`.
  _c "bloc non gardé" NON_GARDE \
     "$(verdict_module_garde 'f() { :; }
if [ "${1:-}" = "--selftest" ]; then
  f; exit $?
fi')"
  _c "bloc gardé par BASH_SOURCE" OK \
     "$(verdict_module_garde 'if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  exit 0
fi')"
  #  Un module qui n'a aucun bloc d'exécution n'a rien à garder.
  _c "module sans bloc" SANS_OBJET "$(verdict_module_garde 'f() { echo ok; }')"
  #  ⚠️ Un `exit` DANS une fonction ne s'exécute pas au sourçage : le refuser
  #  ferait crier le contrôle sur du légitime, et un contrôle qui crie sur du
  #  légitime finit désarmé.
  _c "exit à l'intérieur d'une fonction" SANS_OBJET \
     "$(verdict_module_garde 'f() {
  [ -z "$1" ] && exit 2
}')"

  #  ── La mesure sur le dépôt réel, liste LUE et non recopiée ────────────────
  racine=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
  liste=$(modules_sources_liste "$racine/scripts/exploitation/check-reliability.sh")

  #  🔴 CAS ZÉRO. Une liste vide n'est pas « aucun module fautif » : c'est une
  #  lecture qui a échoué — le motif de la boucle a changé, ou le fichier a
  #  bougé. INCONNU, jamais OK (`standards/04` §1).
  if [ -z "$liste" ]; then
    echo "  ✗ liste des modules introuvable dans check-reliability.sh — le contrôle ne mesure RIEN"
    return 1
  fi
  echo "  · $(printf '%s' "$liste" | wc -w) module(s) sourcé(s) relevés dans check-reliability.sh"

  for m in $liste; do
    fichier="$racine/scripts/lib/lib-$m.sh"
    if [ ! -f "$fichier" ]; then
      echo "  ✗ lib-$m.sh : sourcé par check-reliability.sh et absent du dépôt"
      echecs=$((echecs + 1)); continue
    fi
    obtenu=$(verdict_module_garde "$(cat "$fichier")")
    case "$obtenu" in
      OK|SANS_OBJET) : ;;
      *)
        echo "  ✗ lib-$m.sh : son bloc --selftest n'est pas gardé — il se déclenchera"
        echo "      chez check-reliability.sh, qui sortira AVANT ses propres épreuves."
        echo "      → if [ \"\${BASH_SOURCE[0]}\" = \"\$0\" ] && [ \"\${1:-}\" = \"--selftest\" ]; then"
        echecs=$((echecs + 1))
        ;;
    esac
  done

  if [ "$echecs" -eq 0 ]; then
    echo "✓ lib-modules-sources : aucun module sourcé ne peut interrompre son appelant."
    return 0
  fi
  echo "✗ lib-modules-sources : $echecs cas en échec."
  return 1
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  _modules_sources_selftest
  exit $?
fi
