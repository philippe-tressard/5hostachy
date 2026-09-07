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
echo "  Mémoire       : ~/.claude/projects/C--Dev-5hostachy/memory/"
echo "  Autre projet  : List-dons → C:\\Dev\\List-dons (NE PAS y toucher depuis ici)"
if [ "${COURANT,,}" != "${ATTENDU,,}" ]; then
  echo "  ⚠️  RÉPERTOIRE INATTENDU (attendu $ATTENDU) — signale-le à l'utilisateur"
  echo "      AVANT d'agir : mémoires et étiquette partiront au mauvais endroit."
fi
echo "  → Reprends cette ligne en tête de ta 1ʳᵉ réponse ; si la demande porte"
echo "    sur List-dons, dis-le et propose de relancer depuis C:\\Dev\\List-dons."
echo "════════════════════════════════════════════════════════"
