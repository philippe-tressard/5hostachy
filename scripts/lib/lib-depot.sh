#!/bin/sh
# =============================================================================
#  lib-depot.sh — où vivent les traces du poste : le répertoire git DU clone
#
#  Le pré-check, le rejeu de la CI et le hook `pre-push` déposent leurs traces
#  (`precheck-mep.ok`, `rejeu-ci.ok`, `pr-brief.md`, `erreur-corrigee`,
#  `reecriture-dev`) dans le répertoire git, hors de l'arbre versionné.
#
#  🔴 Ils l'écrivaient `.git/…`, en dur (#1226, 24/09/2026). Dans un worktree
#  (`git worktree add`), `.git` est un FICHIER qui pointe ailleurs : le rejeu
#  complet finissait sur « .git/rejeu-ci.ok: Not a directory », la trace n'était
#  jamais écrite, et le point 16 restait INCONNU. Deux sessions travaillant en
#  parallèle sur le même clone, c'est pourtant le worktree qui les sépare
#  (`standards/13-outillage-claude-code.md` §10).
#
#  `--absolute-git-dir` rend le répertoire PROPRE au worktree : une trace y
#  porte le commit de ce worktree-là, et ne peut pas être prise pour celle du
#  clone principal.
#
#  POSIX : sourcé aussi par `.githooks/pre-push`, qui tourne sous `sh`.
#  Self-test : bash scripts/lib/lib-depot.selftest.sh
# =============================================================================

# dossier_git [répertoire] — chemin absolu du répertoire git, vide et code ≠ 0
# hors d'un dépôt (l'appelant décide : un chemin vide n'est pas « .git »).
dossier_git() {
    git -C "${1:-.}" rev-parse --absolute-git-dir 2>/dev/null
}
