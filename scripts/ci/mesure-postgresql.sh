#!/bin/bash
# =============================================================================
#  mesure-postgresql.sh — Ce que la suite pytest donne sur PostgreSQL (#1747)
#
#  Lancé par le workflow « PostgreSQL », dans `api/`, avec `TESTS_BASE_URL`. Il
#  écrit la MESURE au résumé du run — tests verts, en échec, en erreur, et les
#  fichiers qui échouent le plus : la liste de travail de P2-5.
#
#  Code de sortie (fonction PURE `issue_mesure`, testée par --selftest) :
#    pytest a tourné jusqu'au bout (0 : tout vert, 1 : des échecs) → 0, mesure faite ;
#    toute autre fin (interrompu, erreur interne, usage, rien collecté) → l'échec,
#    parce qu'alors il n'y a PAS de mesure — INCONNU, jamais un vert.
#
#  Test : bash scripts/ci/mesure-postgresql.sh --selftest
# =============================================================================
set -uo pipefail

# ── PURE : $1 code de sortie de pytest → code de sortie de la mesure ──────────
issue_mesure() {
    case "${1:-}" in
        0|1) echo 0 ;;
        '') echo 3 ;;
        *)  echo "$1" ;;
    esac
}

if [ "${1:-}" = "--selftest" ]; then
    fail=0
    for cas in "0:0" "1:0" "2:2" "3:3" "4:4" "5:5" ":3"; do
        entree=${cas%%:*}; voulu=${cas##*:}
        got=$(issue_mesure "$entree")
        if [ "$got" = "$voulu" ]; then echo "PASS  pytest $entree → $got"; else echo "FAIL  pytest $entree → $got (attendu $voulu)"; fail=1; fi
    done
    exit "$fail"
fi

[ -n "${TESTS_BASE_URL:-}" ] || { echo "::error::TESTS_BASE_URL absent : la suite tournerait sur SQLite, et ne mesurerait rien."; exit 3; }

journal=$(mktemp)
python -m pytest tests -q -p no:cacheprovider --tb=no -rfE > "$journal" 2>&1
rc=$?
tail -5 "$journal"

bilan=$(grep -E "^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|error)" "$journal" | tail -1)
resume="${GITHUB_STEP_SUMMARY:-/dev/null}"
{
    echo "## La suite pytest sur PostgreSQL (#1747)"
    echo
    echo "**${bilan:-aucun bilan lu}** — code pytest $rc"
    echo
    echo "### Les fichiers qui échouent le plus"
    echo
    echo "| Échecs | Fichier |"
    echo "|---|---|"
    grep -E "^(FAILED|ERROR) " "$journal" | sed -E 's/^(FAILED|ERROR) ([^:]+)::.*/\2/' \
        | sort | uniq -c | sort -rn | head -40 | awk '{printf "| %s | `%s` |\n", $1, $2}'
} >> "$resume"

exit "$(issue_mesure "$rc")"
