#!/bin/bash
# =============================================================================
#  lib-rotation.sh — Rotation d'un journal SANS jamais délier son inode
#
#  Extrait de `maintenance.sh` le 16/08/2026, quand ce fichier a franchi les 500
#  lignes du rang 1 (`standards/02` §6). La règle est « on découpe QUAND on y
#  touche » : c'est ce bloc-ci qui part, parce que c'est le plus autonome et le
#  seul déjà couvert par un autotest — il emporte donc son contrat avec lui.
#
#  ⚠️ `tail > tmp && mv tmp log` REMPLACE l'inode. Or ces journaux sont tenus
#  OUVERTS : le cron de maintenance y écrit via `>> …log`, health-watch.sh tourne
#  toutes les 5 min et check-reliability.sh toutes les 15 — la rotation dure plus
#  d'une minute et croise donc leurs exécutions. Après le `mv`, leurs écritures
#  partent dans un inode ORPHELIN : invisibles, et perdues à la fin du process.
#  C'est la règle d'or anti-corruption DB (`standards/06` §1) appliquée à un
#  journal — ne jamais délier un fichier qu'un process tient ouvert.
#
#  Constaté le 09/08/2026 : hostachy-maintenance.log s'arrête net à 03:02:55, à
#  la position alphabétique qui précède exactement son propre nom. Tout ce qui
#  suit — la fin du ménage, l'envoi du rapport, et une éventuelle erreur — est
#  illisible. Le défaut avait donc détruit la trace de ses propres conséquences,
#  et masqué pendant une semaine un second bug d'envoi (#301, 16/08/2026).
#
#  `cat tmp > log` réécrit le MÊME inode : les descripteurs ouverts continuent de
#  viser le bon fichier, et le propriétaire est conservé (c'est aussi la cause du
#  `chown` de rattrapage côté appelant — le `mv` repassait le log root-owned et
#  coupait SILENCIEUSEMENT le cron utilisateur auto-deploy, découvert le
#  15/07/2026). Les fd du cron sont en mode APPEND (`>>`) : après troncature, la
#  suite s'écrit à la nouvelle fin, sans trou creux.
#
#  Ce module est SOURCÉ, jamais exécuté par cron → mode 100644.
#  Autotest : bash scripts/lib/lib-rotation.sh --selftest
# =============================================================================

roter_log() {  # $1 = chemin · $2 = lignes conservées → écho : lignes supprimées
    local f=$1 keep=$2 avant apres
    [ -f "$f" ] || { echo 0; return 0; }
    avant=$(wc -l < "$f")
    tail -"$keep" "$f" > "$f.tmp" || { rm -f "$f.tmp"; echo 0; return 1; }
    cat "$f.tmp" > "$f"
    rm -f "$f.tmp"
    apres=$(wc -l < "$f")
    echo $(( avant - apres ))
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
#  Vérifie le COMPORTEMENT, pas la forme : un contrôle qui grepperait « pas de
#  mv » se contournerait sans rien réparer. On ouvre un descripteur en APPEND —
#  ce que font le cron de maintenance, health-watch.sh et check-reliability.sh —
#  on rote, puis on écrit. Si l'inode a été remplacé, la ligne est invisible.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    ok() { echo "PASS  $1"; }
    ko() { echo "FAIL  $1"; st=1; }
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT

    j="$tmp/hostachy-faux.log"
    seq 1 100 > "$j"
    exec 9>>"$j"                    # un process concurrent tient le journal ouvert
    sup=$(roter_log "$j" 10)
    echo "ecrit-apres-rotation" >&9
    exec 9>&-

    [ "$sup" = "90" ] && ok "rotation : 90 lignes supprimées" \
                      || ko "rotation : 90 attendu, obtenu '$sup'"
    grep -q "ecrit-apres-rotation" "$j" \
        && ok "un descripteur déjà ouvert écrit toujours dans le fichier VISIBLE" \
        || ko "inode délié : l'écriture d'un process concurrent est PERDUE (09/08/2026)"
    [ "$(head -1 "$j")" = "91" ] \
        && ok "ce sont bien les dernières lignes qui restent" \
        || ko "contenu conservé inattendu : $(head -1 "$j")"
    [ ! -e "$j.tmp" ] && ok "pas de .tmp résiduel" || ko ".tmp résiduel"

    # Cas zéro (socle 04 §2) : un journal absent ne doit pas faire échouer le
    # ménage — `set -e` ferait alors sauter l'envoi du rapport qui suit.
    z=$(roter_log "$tmp/absent.log" 10) && [ "$z" = "0" ] \
        && ok "journal absent : 0 ligne, pas d'erreur" \
        || ko "journal absent mal traité ('$z')"

    [ $st -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $st
fi
