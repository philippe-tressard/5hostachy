#!/usr/bin/env bash
# =============================================================================
#  RELAIS PERMANENT — le script vit dans scripts/exploitation/.
#
#  Il n'existe que pour une raison : l'unité systemd désigne CE chemin absolu,
#  et rien dans un déploiement ne la met à jour. Sans ce relais, le garde-fou de
#  rôle au démarrage pointerait dans le vide sur les deux nœuds — donc plus
#  aucune protection anti-split-brain APRÈS UNE COUPURE DE COURANT, précisément
#  le moment où personne ne regarde.
#
#  Les six autres relais ont été retirés le 16/08/2026 : plus aucun cron ne
#  désignait la racine, vérifié sur les deux nœuds (cron root, cron ptressard,
#  unités systemd). Ce fichier est donc le SEUL survivant, et volontairement.
#
#  ⚠️ Celui-ci NE PART PAS, contrairement aux autres relais (#337, 15/08/2026).
#  L'unité systemd le désigne, et la modifier demande d'écrire dans
#  /etc/systemd/system/ — ce que l'allowlist sudo de rpi2 n'autorise pas (#302).
#  Le choix assumé est de garder ce relais plutôt que d'exiger une intervention
#  root de plus sur le garde-fou anti-split-brain.
# =============================================================================
exec "$(dirname "$0")/scripts/exploitation/boot-role-guard.sh" "$@"
