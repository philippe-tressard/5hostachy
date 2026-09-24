#!/bin/bash
# =============================================================================
#  lib-depot.selftest.sh — éprouve `dossier_git` sur un VRAI worktree (#1226)
#
#  Un test qui ne créerait qu'un clone ne dirait rien : `.git` y est un
#  répertoire, et l'écriture en dur y marchait déjà. Le cas qui a échoué est le
#  worktree, où `.git` est un fichier — il est donc construit ici, dans un
#  dossier temporaire, puis effacé.
#
#  Lancer : bash scripts/lib/lib-depot.selftest.sh   (job CI `test-scripts`)
# =============================================================================
set -u
. "$(dirname "$0")/lib-depot.sh"

fail=0
check() { # description condition(0/1)
    if [ "$2" = 0 ]; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
git init -q "$TMP/clone"
git -C "$TMP/clone" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
git -C "$TMP/clone" worktree add -q "$TMP/wt" -b essai 2>/dev/null

echo "== self-test lib-depot.dossier_git =="
D_CLONE=$(dossier_git "$TMP/clone")
D_WT=$(dossier_git "$TMP/wt")
[ -d "$D_CLONE" ]; check "clone : un répertoire" $?
[ -f "$TMP/wt/.git" ]; check "worktree : .git y est bien un FICHIER (le cas qui échouait)" $?
[ -d "$D_WT" ]; check "worktree : dossier_git rend un répertoire" $?
[ "$D_WT" != "$D_CLONE" ]; check "worktree : son propre répertoire, pas celui du clone" $?
( : > "$D_WT/rejeu-ci.ok" ) 2>/dev/null; check "worktree : une trace s'y écrit" $?
D_HORS=$(dossier_git "$TMP"); r=$?
[ -z "$D_HORS" ] && [ "$r" != 0 ]; check "hors dépôt : chemin vide et code d'échec, jamais « .git »" $?

[ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
exit $fail
