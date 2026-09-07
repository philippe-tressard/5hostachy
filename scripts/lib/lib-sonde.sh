#!/usr/bin/env bash
# =============================================================================
#  lib-sonde.sh — la sonde HTTP, écrite UNE fois.
#
#  Elle existait en TROIS exemplaires le 01/09/2026 — `health-watch.sh`,
#  `lib-verdicts.sh` (pour check-reliability) et `precheck-mep.sh` — et le
#  troisième avait déjà divergé : ni garde sur la sortie vide, ni timeout par
#  défaut. C'est la duplication ordinaire, celle qui ne se voit pas parce que la
#  fonction tient en trois lignes.
#
#  ⚠️ Et elle a déjà coûté. Le commentaire de `health-watch.sh` le dit :
#
#  > `curl -w '%{http_code}'` écrit DÉJÀ « 000 » quand la requête échoue ; le
#  > `|| echo 000` historique en ajoutait une seconde, d'où les « HTTP 000000 »
#  > des logs de la nuit du 30/07/2026. […] la même construction rendait un
#  > contrôle de check-reliability.sh faussement VERT (comparaison d'entiers sur
#  > « 0\n0 »).
#
#  Le correctif avait été porté dans deux copies sur trois. Une sonde ne rend
#  qu'UNE valeur, et il n'y a qu'un endroit où l'écrire.
#
#  Ce module ne dépend de rien : il est sourçable par un script d'exploitation
#  comme par un script de poste, avant tout le reste.
# =============================================================================

# ── Sonde HTTP — UNE valeur, toujours ────────────────────────────────────────
http_code() {  # $1 = URL, $2 = timeout (défaut 10) → code HTTP ou 000
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-10}" "$1" 2>/dev/null)
  echo "${code:-000}"
}
