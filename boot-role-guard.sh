#!/usr/bin/env bash
# =============================================================================
#  RELAIS TEMPORAIRE — le script vit désormais dans scripts/exploitation/.
#
#  Il n'existe que pour une raison : les tâches cron et l'unité systemd
#  désignent CE chemin absolu, et rien dans un déploiement ne les met à jour.
#  Sans ce relais, fusionner ferait pointer les six points d'entrée dans le vide
#  sur les deux nœuds en cinq minutes — plus de bascule, plus de failover, plus
#  de contrôles, et AUCUNE alerte, puisque le producteur d'alertes fait partie de
#  ce qui ne démarre plus.
#
#  À RETIRER une fois les points d'entrée basculés vers scripts/exploitation/ ET
#  la bascule de 02:00 constatée sur les deux nœuds — dans une PR séparée (#337).
#  Tant qu'ils sont là, `bash scripts/poste/verifier-points-entree.sh` reste vert
#  sur les anciens chemins : c'est voulu, c'est la définition d'un relais.
# =============================================================================
exec "$(dirname "$0")/scripts/exploitation/boot-role-guard.sh" "$@"
