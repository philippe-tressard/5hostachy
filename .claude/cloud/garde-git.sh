#!/usr/bin/env bash
# garde-git.sh — Relais, en session CLOUD seulement, vers le garde-fou du socle
# qui refuse les gestes git destructeurs (`reset --hard`, `clean -f`…).
#
# POURQUOI (24/09/2026). Sur le poste, ce garde-fou est un hook de
# `~/.claude/settings.json` ; le cloud ne lit pas `~/.claude`, et la seule règle
# que l'utilisateur a demandé de rendre inévitable y disparaissait sans un mot.
# Le relais vit donc dans les réglages DU DÉPÔT, qui voyagent avec lui.
#
# Il ne réécrit pas le garde-fou : il appelle celui de `claude-config`, cloné par
# `.claude/cloud/setup.sh`. Sur le poste il ne fait rien — le hook global y tourne
# déjà, et deux passages rendraient deux décisions pour un geste.
# Garde-fou absent (dépôt non attaché) : rien à relayer, et `env-report.sh` le
# déclare ABSENT à chaque session plutôt que de laisser croire à une protection.
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] || exit 0
GARDE="$HOME/claude-config/bin/garde-git-destructif.py"
[ -f "$GARDE" ] || exit 0
exec python3 "$GARDE"
