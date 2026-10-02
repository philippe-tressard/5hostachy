#!/usr/bin/env bash
# =============================================================================
#  lib-health-watch.sh — C31 : health-watch, qui DÉCIDE du failover, sonde-t-il ?
#
#  Né de #1586 (audit du 02/10/2026). `health-watch.sh` ne disait RIEN quand le
#  site répondait : `if [ "$HTTP_CODE" = "200" ]; then … exit 0`. Sur les deux
#  nœuds, la dernière ligne de son journal datait du 30/09 22:42 — 34 h de
#  silence pour un cron */5, indiscernables d'un script mort. Et aucun contrôle
#  ne mesurait son passage : C14 surveille auto-deploy, C15 check-reliability,
#  C12 ne lit ce journal que pour les verrous orphelins. Un cron perdu, un bit x
#  retiré, un module absent avant la sonde ou un verrou bloqué rendaient le
#  failover automatique INEXISTANT, et vingt-neuf contrôles restaient verts.
#
#  Le motif est celui d'auto-deploy et de C14 (mémoire `battement_auto_deploy`,
#  31/07/2026) : une ligne DATÉE à chaque passage, valable dans les DEUX rôles,
#  et un contrôle qui mesure l'ÂGE de la dernière — `beat_age_min` et
#  `beat_verdict` (lib-verdicts.sh), les mêmes que C14, C15 et C17.
#
#  ⚠️ Le battement n'est pas « une ligne datée quelconque » mais la ligne de la
#  SONDE publique, écrite juste après elle, avant toute décision. « Autre
#  instance en cours » ou « Hostname inconnu » sont datés aussi, et pourtant ce
#  passage-là n'a rien sondé : les compter ferait un vert sur un verrou bloqué.
#
#  Trois morceaux d'une même notion, ensemble pour qu'un changement de l'un
#  casse les épreuves de l'autre :
#    ligne_sonde_publique   ce que health-watch ÉCRIT (son battement) ;
#    collecte_battement_hw  ce que la collecte en LIT sur chaque nœud ;
#    healthwatch_verdicts   ce que check-reliability en CONCLUT (C31).
#
#  Chaque nœud mesure les DEUX ; le constat ne nomme qu'un nœud, et la
#  répartition de `lib-notification.sh` le fait donc dire UNE fois, par ce nœud
#  — ou par l'autre s'il est muet (#1402). Comme C15 : battement absent ou
#  illisible = FAIL, jamais OK. Le failover est la seule reprise automatique.
#
#  SOURCÉ (mode 100644) par `health-watch.sh` (la ligne) et `lib-collecte.sh`
#  (la collecte, puis les verdicts appelés par `check-reliability.sh`).
#  ⚠️ `healthwatch_verdicts` emploie `ok`, `fail`, `$SELF`, `$PEER`, `$PEER_OK`
#  et les champs S_*/P_* de son appelant.
#  Autotest : bash scripts/lib/lib-health-watch.sh --selftest
# =============================================================================

#  4 passages de 5 min manqués : le régime du cron (*/5), comme C14. Un
#  passage de failover dure moins de deux minutes (30 s + 20 s d'attente).
HW_MAX_AGE_MIN=20
#  Le motif du battement, UNE fois : la collecte le reçoit d'ici, et
#  l'autotest vérifie que les deux lignes de `ligne_sonde_publique` y répondent.
#  ASCII seulement : il voyage par SSH, et le « ⚠ » du cas HS le précède.
HW_MOTIF_SONDE='Site (OK|HS) \(HTTP '

# ── La ligne de la sonde publique (PURE) ─────────────────────────────────────
ligne_sonde_publique() { # $1 = code HTTP, $2 = ce nœud
    if [ "${1:-}" = 200 ]; then echo "Site OK (HTTP 200) — RPi: ${2:-?}"
    else echo "⚠ Site HS (HTTP ${1:-000}) — RPi: ${2:-?}"; fi
}

# ── La collecte : la date de la dernière SONDE, sur chaque nœud ──────────────
#  Rend un fragment de COLLECT (une ligne `healthwatch_dernier=…`) pour le
#  journal $1 — paramétré pour que l'autotest l'EXÉCUTE sur un journal témoin
#  au lieu de relire le motif (`standards/04` §22). Journal absent ou sans
#  sonde : valeur vide, que `beat_age_min` traduit en INCONNU.
#  `tail -400` : un passage en panne écrit une dizaine de lignes, dont une sonde.
collecte_battement_hw() { # $1 = journal de health-watch
    printf '\necho "healthwatch_dernier=$(tail -400 %s 2>/dev/null | grep -E "%s" | tail -1 | cut -c2-20)"\n' \
        "$1" "$HW_MOTIF_SONDE"
}
COLLECT_HW=$(collecte_battement_hw /var/log/hostachy-health-watch.log)

# ── Le contrôle statique : la ligne est écrite AVANT la décision ─────────────
#  PURE (lit un texte). OK si `ligne_sonde_publique` est appelée avant le test
#  du code 200 — l'endroit exact où le script sortait en silence.
#  → OK | ABSENT | APRES
battement_avant_decision() { # $1 = fichier
    awk '
        /^[[:space:]]*#/ { next }
        !b && /ligne_sonde_publique "\$HTTP_CODE"/ { b = NR }
        !d && /"\$HTTP_CODE" = "200"/             { d = NR }
        END { if (!b) print "ABSENT"; else if (d && b > d) print "APRES"; else print "OK" }
    ' "$1"
}

# ── C31. health-watch sonde-t-il encore, sur les DEUX nœuds ? ────────────────
healthwatch_verdicts() {
    local n v age
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then v=${S_healthwatch_dernier:-}
        else [ "$PEER_OK" -eq 0 ] || continue; v=${P_healthwatch_dernier:-}; fi
        age=$(beat_age_min "$v")
        case "$(beat_verdict "$age" "$HW_MAX_AGE_MIN")" in
            ok)     ok   "health-watch sonde sur $n : dernier passage il y a ${age} min" ;;
            absent) fail "health-watch ne sonde plus sur $n : dernier passage il y a ${age} min (attendu ≤ ${HW_MAX_AGE_MIN}) → plus de failover automatique par ce nœud (cron perdu, bit x, script en erreur avant la sonde, verrou bloqué)" ;;
            *)      fail "health-watch INCONNU sur $n : aucune sonde datée dans /var/log/hostachy-health-watch.log (journal absent, illisible ou format changé) → le failover automatique n'est pas prouvé" ;;
        esac
    done
}

# ── Autotest (job CI `test-scripts`) ──────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { if [ "$3" = "$2" ]; then echo "PASS  $1 → ${3:-(rien)}"
          else echo "FAIL  $1  attendu=${2:-(rien)} obtenu=${3:-(rien)}"; st=1; fi; }
    ICI=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    # shellcheck source=lib-verdicts.sh
    . "$ICI/lib-verdicts.sh"     # beat_age_min, beat_verdict
    tmp=$(mktemp -d)
    il_y_a() { date -d "@$(( $(date +%s) - $1 * 60 ))" '+%Y-%m-%d %H:%M:%S'; }

    echo "== C31 : la ligne écrite répond au motif lu =="
    for c in 200 503 000; do
        t "sonde HTTP $c → reconnue comme battement" 1 \
          "$(ligne_sonde_publique "$c" rpi1 | grep -cE "$HW_MOTIF_SONDE")"
    done
    t "« Autre instance en cours » n'est PAS un battement" 0 \
      "$(echo "Autre instance en cours — abandon." | grep -cE "$HW_MOTIF_SONDE")"

    echo "== C31 : la collecte, exécutée sur un journal témoin =="
    {
        echo "[2026-10-02 09:00:01] $(ligne_sonde_publique 200 rpi2)"
        echo "[2026-10-02 09:05:01] $(ligne_sonde_publique 502 rpi2)"
        echo "[2026-10-02 09:05:01]   Ce RPi (rpi2) est l'actif — pas d'intervention (surveillance assurée par le standby)."
        echo "[2026-10-02 09:10:01] Autre instance en cours — abandon."
    } > "$tmp/hw.log"
    t "la dernière SONDE, pas la dernière ligne datée" "healthwatch_dernier=2026-10-02 09:05:01" \
      "$(bash -c "$(collecte_battement_hw "$tmp/hw.log")")"
    t "journal absent → valeur vide (INCONNU)" "healthwatch_dernier=" \
      "$(bash -c "$(collecte_battement_hw "$tmp/absent.log")")"
    if bash -n <(printf '%s' "$COLLECT_HW") 2>/dev/null; then echo "PASS  COLLECT_HW est du shell valide"
    else echo "FAIL  COLLECT_HW est du shell INVALIDE (apostrophe dans la chaîne ?)"; st=1; fi

    echo "== C31 : les verdicts, sur les DEUX nœuds =="
    ok()   { echo "[ OK ] $*"; }
    fail() { echo "[FAIL] $*"; }
    SELF=rpi1 PEER=rpi2 PEER_OK=0
    S_healthwatch_dernier=$(il_y_a 3) P_healthwatch_dernier=$(il_y_a 3)
    sortie=$(healthwatch_verdicts)
    t "deux battements frais → deux OK" "2|0" "$(grep -c '^\[ OK \]' <<< "$sortie")|$(grep -c '^\[FAIL\]' <<< "$sortie")"
    #  Le cas du ticket : le journal muet depuis le 30/09 22:42, relu 34 h plus
    #  tard — exactement ce que l'ancien script laissait voir quand tout allait bien.
    P_healthwatch_dernier=$(il_y_a 2040)
    sortie=$(healthwatch_verdicts)
    t "faute injectée : silence de 34 h sur rpi2 (#1586) → FAIL" 1 \
      "$(grep -c '^\[FAIL\] health-watch ne sonde plus sur rpi2' <<< "$sortie")"
    #  Une ligne par nœud, qui ne nomme QUE lui : c'est ce qui la fait dire une
    #  fois (#1402). Si elle nommait les deux, les deux nœuds l'enverraient.
    t "…et ce constat ne nomme pas rpi1" 0 "$(grep '^\[FAIL\]' <<< "$sortie" | grep -c rpi1)"
    P_healthwatch_dernier=$(il_y_a 21)
    t "un passage de plus que le seuil → FAIL" 1 "$(healthwatch_verdicts | grep -c '^\[FAIL\]')"
    P_healthwatch_dernier=$(il_y_a 19)
    t "un passage de moins → OK" 0 "$(healthwatch_verdicts | grep -c '^\[FAIL\]')"
    #  Cas zéro : rien lu n'est PAS un vert.
    P_healthwatch_dernier=""
    t "aucune sonde lue sur rpi2 → FAIL INCONNU, jamais OK" 1 \
      "$(healthwatch_verdicts | grep -c '^\[FAIL\] health-watch INCONNU sur rpi2')"
    P_healthwatch_dernier="pas une date"
    t "horodatage illisible → FAIL INCONNU" 1 "$(healthwatch_verdicts | grep -c 'INCONNU sur rpi2')"
    PEER_OK=255
    t "pair injoignable : rien sur rpi2 (C15 et le pair muet le disent)" 0 "$(healthwatch_verdicts | grep -c rpi2)"

    echo "== C31 : health-watch écrit sa ligne AVANT de décider =="
    t "health-watch.sh : battement avant le test du 200" OK \
      "$(battement_avant_decision "$ICI/../exploitation/health-watch.sh")"
    #  La forme d'avant #1586 : la branche 200 sortait sans rien écrire.
    printf '%s\n' 'HTTP_CODE=$(http_code "$PUBLIC_URL")' 'if [ "$HTTP_CODE" = "200" ]; then' \
        '    rm -f "$COOLDOWN_FILE"; exit 0' 'fi' 'log "⚠ Site HS (HTTP $HTTP_CODE) — RPi: $SELF"' > "$tmp/avant.sh"
    t "faute injectée : la forme du 30/09 (200 muet) → refusée" ABSENT "$(battement_avant_decision "$tmp/avant.sh")"
    printf '%s\n' 'if [ "$HTTP_CODE" = "200" ]; then exit 0; fi' \
        'log "$(ligne_sonde_publique "$HTTP_CODE" "$SELF")"' > "$tmp/apres.sh"
    t "faute injectée : battement écrit APRÈS la sortie 200 → refusé" APRES "$(battement_avant_decision "$tmp/apres.sh")"

    rm -rf "$tmp"
    [ "$st" -eq 0 ] && echo "lib-health-watch : tous les cas passent."
    exit "$st"
fi
