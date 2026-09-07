#!/usr/bin/env bash
# =============================================================================
#  Conformité des points d'entrée d'un nœud à ce que le dépôt attend.
#
#  POURQUOI. Les tâches cron et l'unité systemd qui lancent l'exploitation
#  n'étaient écrites nulle part : il fallait ouvrir un terminal sur chaque nœud
#  pour savoir ce qui tourne. `check-reliability.sh` C18 compare bien les deux
#  nœuds, mais ENTRE EUX — deux crontabs identiquement périmés lui paraissent
#  parfaits. Ce contrôle-ci compare au **dépôt**, ce qui attrape aussi la dérive
#  commune.
#
#  CE QU'IL NE FAIT PAS : écrire quoi que ce soit sur un nœud. Poser un crontab
#  reste un geste explicite, un nœud à la fois.
#
#  Usage : bash scripts/poste/verifier-points-entree.sh [ptressard@IP …]
#          bash scripts/poste/verifier-points-entree.sh --selftest
# =============================================================================
set -uo pipefail

RACINE_DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
ATTENDU="$RACINE_DEPOT/infra/points-entree"
NOEUDS_DEFAUT="ptressard@192.168.1.222 ptressard@192.168.1.223"

# ── Fonctions de décision PURES ──────────────────────────────────────────────
#  Extraites dans `lib-points-entree.sh` le 15/08/2026 (#352) : `check-reliability.sh`
#  surveille désormais le MÊME invariant en continu, sur les nœuds, et deux
#  normalisations de crontab qui divergent donneraient deux verdicts opposés sans
#  qu'on sache lequel croire. Le self-test est parti avec elles — il est leur contrat.
# shellcheck source=../lib/lib-points-entree.sh
. "$(dirname "$0")/../lib/lib-points-entree.sh"

if [ "${1:-}" = "--selftest" ]; then points_entree_selftest; exit $?; fi

# ── Exécution ────────────────────────────────────────────────────────────────

sur() { timeout 25 ssh -o BatchMode=yes -o ConnectTimeout=8 "$1" "$2" 2>/dev/null; }

global=0
for noeud in ${*:-$NOEUDS_DEFAUT}; do
  echo "═══ $noeud ═══"

  #  `sudo -n` est refusé sur rpi2 (#302) : la sortie sera vide, et le verdict
  #  INCONNU le dira au lieu de prétendre à un écart.
  for couple in "cron-root.crontab:sudo -n crontab -l" \
                "cron-ptressard.crontab:crontab -l"; do
    fichier="${couple%%:*}"; commande="${couple#*:}"
    att=$(normaliser_cron < "$ATTENDU/$fichier")
    ins=$(sur "$noeud" "$commande" | normaliser_cron)
    v=$(verdict_conformite "$att" "$ins")
    printf "  %-26s %s\n" "$fichier" "$v"
    [ "$v" = "ECART" ] && { diff <(printf '%s\n' "$att") <(printf '%s\n' "$ins") | sed 's/^/      /'; global=1; }
    [ "$v" = "INCONNU" ] && global=2
  done

  att=$(normaliser_unit < "$ATTENDU/hostachy-role-guard.service")
  ins=$(sur "$noeud" 'cat /etc/systemd/system/hostachy-role-guard.service' | normaliser_unit)
  v=$(verdict_conformite "$att" "$ins")
  printf "  %-26s %s\n" "hostachy-role-guard.service" "$v"
  [ "$v" = "ECART" ] && { diff <(printf '%s\n' "$att") <(printf '%s\n' "$ins") | sed 's/^/      /'; global=1; }
  [ "$v" = "INCONNU" ] && global=2

  #  Le fichier peut être conforme et le service désactivé : la conformité du
  #  texte ne dit rien de l'état. Ni l'un ni l'autre ne prouve qu'il FONCTIONNE —
  #  cela ne s'observe qu'au démarrage (redémarrer le standby, qui ne sert rien).
  etat=$(sur "$noeud" 'systemctl is-enabled hostachy-role-guard.service')
  printf "  %-26s %s\n" "  → service activé" "${etat:-INCONNU}"
  [ "$etat" = "enabled" ] || global=1
done

case "$global" in
  0) echo; echo "✓ Points d'entrée conformes au dépôt." ;;
  2) echo; echo "? Au moins un point n'a pas pu être lu — INCONNU, pas OK." ;;
  *) echo; echo "✗ Écart entre le dépôt et un nœud : corriger le nœud, ou le dépôt s'il a raison." ;;
esac
exit "$global"
