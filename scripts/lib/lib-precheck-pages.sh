#!/bin/bash
# =============================================================================
#  lib-precheck-pages.sh — point 20 du pré-check : l'ordre du menu SERVI (#1114)
#
#  `pages_order` est une donnée de production, que l'administration réordonne ;
#  aucun test de CI ne la voit. La décision vit dans
#  `front/scripts/sonde-pages-order.mjs` (pure, self-testée, et qui lit la table
#  des pages du CODE par `lib-pages.mjs`) — ce module ne fait que la lancer et
#  rapporter son verdict. Un fantôme rend ÉCART (le menu l'écarte) ; une
#  répétition rend FAIL (l'écran figé du 16/09/2026).
#
#  Sourcé par `scripts/poste/precheck-mep.sh`, qui fournit `rapporter` et `SITE`.
# =============================================================================

precheck_point_pages() {
  local sortie verdict detail
  if ! command -v node >/dev/null 2>&1; then
    rapporter 20 INCONNU "Ordre du menu servi par la production" "node absent du poste"
    return
  fi
  sortie=$(node "$RACINE_DEPOT/front/scripts/sonde-pages-order.mjs" --site "$SITE" 2>/dev/null)
  verdict="${sortie%%$'\t'*}"
  detail="${sortie#*$'\t'}"
  case "$verdict" in OK|ECART|FAIL|INCONNU) ;; *) verdict=INCONNU; detail="sonde muette" ;; esac
  rapporter 20 "$verdict" "Ordre du menu servi par la production" "$detail"
}
