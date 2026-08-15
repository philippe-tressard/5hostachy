#!/usr/bin/env bash
# =============================================================================
#  RELAIS PERMANENT — le script vit dans scripts/exploitation/.
#
#  Il n'existe que pour une raison : les tâches cron et l'unité systemd
#  désignent CE chemin absolu, et rien dans un déploiement ne les met à jour.
#  Sans ce relais, fusionner ferait pointer les six points d'entrée dans le vide
#  sur les deux nœuds en cinq minutes — plus de bascule, plus de failover, plus
#  de contrôles, et AUCUNE alerte, puisque le producteur d'alertes fait partie de
#  ce qui ne démarre plus.
#
#  ⚠️ Celui-ci NE PART PAS, contrairement aux autres relais (#337, 15/08/2026).
#  L'unité systemd le désigne, et la modifier demande d'écrire dans
#  /etc/systemd/system/ — ce que l'allowlist sudo de rpi2 n'autorise pas (#302).
#  Le choix assumé est de garder ce relais plutôt que d'exiger une intervention
#  root de plus sur le garde-fou anti-split-brain.
# =============================================================================
exec "$(dirname "$0")/scripts/exploitation/boot-role-guard.sh" "$@"
