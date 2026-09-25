#!/bin/bash
# env-report.sh — Rapport d'environnement injecté au démarrage de session.
# Objectif : rendre IMPOSSIBLE de travailler sur le mauvais projet sans le voir.
# L'étiquette de session et la banque de mémoire découlent du répertoire de
# lancement, pas du contenu de la demande : une session ouverte ailleurs et
# pilotée en chemins absolus écrit ses mémoires au mauvais endroit et n'exécute
# pas ce pré-flight (constaté le 31/07/2026).
ATTENDU="/c/Dev/5hostachy"
COURANT=$(pwd)
echo "═══════════════ ENVIRONNEMENT DE TRAVAIL ═══════════════"
echo "  Projet        : 5Hostachy (copropriété — prod HA sur 2 RPi)"
echo "  Étiquette     : 5Hostachy — <sujet>"
echo "  Répertoire    : $COURANT"
echo "  Dépôt/branche : $(git config --get remote.origin.url 2>/dev/null) [$(git branch --show-current 2>/dev/null)]"
[ "${CLAUDE_CODE_REMOTE:-}" = "true" ] \
  || echo "  Mémoire       : ~/.claude/projects/C--Dev-5hostachy/memory/"
echo "  Autre projet  : List-dons → C:\\Dev\\List-dons (NE PAS y toucher depuis ici)"
if [ "${CLAUDE_CODE_REMOTE:-}" = "true" ]; then
  # Session CLOUD (claude.ai/code) — le répertoire attendu n'y a pas de sens.
  # Ce bloc est le contrôle de `.claude/cloud/setup.sh` : il relit à CHAQUE
  # session ce que le setup a posé, et déclare ABSENT ce qui manque au lieu de
  # laisser croire que tout est là (socle 04 : INCONNU, jamais OK).
  echo "  Session       : ☁️  CLOUD — pas de SSH : pré-check INCONNU, post-check au poste."
  echo "                  La MEP s'enchaîne SANS validation jusqu'à main (CLAUDE.md, « Session cloud »)."
  echo "  Mémoire       : banque du poste ABSENTE — rien de ce qui s'écrit ici n'est gardé."
  [ -d front/node_modules ] \
    && echo "  Dépendances   : présentes" \
    || echo "  Dépendances   : 🔴 ABSENTES — lancer : bash .claude/cloud/setup.sh"
  [ -f "$HOME/.claude/standards/INDEX.md" ] \
    && echo "  Socle         : présent (~/.claude/standards/)" \
    || echo "  Socle         : 🔴 ABSENT — claude-config non attaché à la session"
  GARDE="$HOME/claude-config/bin/garde-git-destructif.py"
  if [ -f "$GARDE" ] && timeout 5 python3 "$GARDE" --selftest >/dev/null 2>&1; then
    echo "  Garde-fou git : actif (autotest passé)"
  else
    echo "  Garde-fou git : 🔴 ABSENT — RIEN ne refuse \`git reset --hard\`, \`clean -f\`,"
    echo "                  \`push --force\` : ces gestes restent INTERDITS sans l'accord de Philippe."
  fi
elif [ "${COURANT,,}" != "${ATTENDU,,}" ]; then
  echo "  ⚠️  RÉPERTOIRE INATTENDU (attendu $ATTENDU) — signale-le à l'utilisateur"
  echo "      AVANT d'agir : mémoires et étiquette partiront au mauvais endroit."
fi
echo "  → Reprends cette ligne en tête de ta 1ʳᵉ réponse ; si la demande porte"
echo "    sur List-dons, dis-le et propose de relancer depuis C:\\Dev\\List-dons."
echo "════════════════════════════════════════════════════════"
