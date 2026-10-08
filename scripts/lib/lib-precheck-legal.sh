#!/bin/bash
# =============================================================================
#  lib-precheck-legal.sh — point 21 du pré-check : les textes légaux SERVIS
#                          sont-ils complets ? (#1585, 08/10/2026)
#
#  La politique de confidentialité et les mentions légales vivent EN BASE
#  (`config_site`), éditables depuis Admin › Légal. Le gabarit du seed laisse
#  « À RENSEIGNER » ce qui dépend de l'instance (éditeur, prestataires) : un
#  texte servi qui en porte encore une est une page publique INCOMPLÈTE. Quatre
#  sont restées servies jusqu'au 08/10/2026 sans que rien ne le dise — aucun test
#  de CI ne pouvait le voir, la donnée étant en base.
#
#  Ce point lit la page SERVIE (`/api/config/legal`, publique), jamais le seed :
#  corriger le gabarit ne corrige pas l'instance. Il compte sur les OCTETS de la
#  réponse — un premier comptage en Python sous Windows avait rendu 0, faux vert
#  dû à l'encodage de l'entrée standard (#1585).
#
#  ÉCART et non ÉCHEC : compléter un texte est un geste d'administration, pas un
#  défaut du lot ; il ne doit pas bloquer une MEP, mais il se DIT à chacune.
#
#  Sourcé par `scripts/poste/precheck-mep.sh`, qui fournit `rapporter` et `SITE`.
#  Autotest : bash scripts/lib/lib-precheck-legal.sh --selftest
# =============================================================================

#  Le verdict, isolé pour être testable sans réseau. (PURE)
#    $1 = corps de `/api/config/legal` → OK | ECART:<n> | INCONNU
verdict_textes_legaux() {
  local corps="${1:-}" n
  #  Cas zéro : une réponse vide, ou qui n'est pas la bonne, n'a rien mesuré.
  case "$corps" in
    *politique_confidentialite*) ;;
    *) echo INCONNU; return ;;
  esac
  n=$(printf '%s' "$corps" | grep -o 'RENSEIGNER' | wc -l | tr -d ' ')
  [ "$n" -eq 0 ] && echo OK || echo "ECART:$n"
}

precheck_point_legal() {
  local corps v
  corps=$(curl -s --max-time 15 "$SITE/api/config/legal" 2>/dev/null)
  v=$(verdict_textes_legaux "$corps")
  case "$v" in
    OK)      rapporter 21 OK "Textes légaux servis complets" "aucun « À RENSEIGNER » dans la page servie" ;;
    ECART:*) rapporter 21 ECART "Textes légaux servis complets" \
               "${v#ECART:} « À RENSEIGNER » servi(s) — à compléter dans Admin › Légal (#1585)" ;;
    *)       rapporter 21 INCONNU "Textes légaux servis complets" "réponse illisible de $SITE/api/config/legal" ;;
  esac
}

#  ── Auto-test : la décision se vérifie sans réseau ─────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
  echecs=0
  attendu() {
    local att="$1" obtenu
    obtenu=$(verdict_textes_legaux "$2")
    if [ "$obtenu" = "$att" ]; then echo "PASS  $3 → $obtenu"
    else echo "FAIL  $3  attendu=$att obtenu=$obtenu"; echecs=$((echecs + 1)); fi
  }
  attendu OK       '{"politique_confidentialite": "<p>OVH SAS</p>", "mentions_legales": "x"}' "page complète"
  #  Le cas du 08/10/2026 : quatre mentions encore servies.
  attendu ECART:2  '{"politique_confidentialite": "<strong>À RENSEIGNER</strong> a <strong>À RENSEIGNER</strong>"}' "deux mentions"
  attendu INCONNU  ''                       "réponse vide — rien de mesuré"
  attendu INCONNU  '{"detail":"Not Found"}' "mauvaise réponse — rien de mesuré"
  [ $echecs -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
  exit $echecs
fi
