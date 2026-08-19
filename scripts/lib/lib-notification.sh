#!/bin/bash
# =============================================================================
#  lib-notification.sh — À qui rend compte une exécution de contrôles ?
#                        (module à sourcer)
#
#  POURQUOI ce module existe (#449, mesuré le 19/08/2026) :
#    `check-reliability.sh` n'alertait que `si [ "$FAILS" -gt 0 ]`. Or CINQ de
#    ses contrôles rendent WARN par choix assumé — C16 (cache de build), C17
#    (maintenance en retard), C19 (journal ⇆ base), C20 (sudo), C22 (points
#    d'entrée) — au motif, écrit dans le script, que « cela ne coupe pas la
#    production, et un FAIL à */15 enverrait un mail par heure jusqu'à
#    correction ».
#
#    Le raisonnement était juste sur la FRÉQUENCE et faux sur la CONCLUSION :
#    on en a déduit « pas de mail » là où il fallait « pas ce mail-là ». Ces
#    cinq contrôles n'avaient donc AUCUN destinataire — `standards/04` §7 — et
#    leur verdict finissait dans un journal que personne n'ouvre.
#
#  🔴 CE QUE ÇA A COÛTÉ, et ce n'est pas théorique. Le 16/08/2026 à 03:02, le
#    rapport de la maintenance hebdomadaire a été refusé par l'API (HTTP 422).
#    C19 l'a VU au passage suivant — « elle a TOURNÉ (journal) mais son rapport
#    n'est pas arrivé en base » — et a rendu WARN. Personne n'a été prévenu.
#    Le défaut a été trouvé le 18 à l'œil, sur l'écran d'administration, par
#    l'utilisateur. La détection marchait ; la NOTIFICATION, encore une fois,
#    non — exactement l'incident du 26/07/2026 qui avait fait naître
#    `lib-alert.sh`, un cran plus loin.
#
#  Deux canaux, deux rythmes : l'échec critique alerte dans l'heure, le point de
#  vigilance se résume une fois par jour. La fréquence se règle par le COOLDOWN,
#  jamais en coupant le canal.
#
#  Usage :
#    source /opt/5hostachy/scripts/lib/lib-notification.sh
#    notifier_verdicts "$REPO" "$SELF" "$FAILS" "$WARNS" "$FAIL_LINES" "$WARN_LINES"
#
#  La DÉCISION (`verdict_notification`) est pure et vit dans `lib-verdicts.sh`,
#  avec son contrat dans `verdicts_selftest`. Ce module-ci ne porte que l'envoi.
#
#  Ce module est SOURCÉ, jamais exécuté par cron → mode 100644 (le job CI
#  `test-scripts` le vérifie ; un bit d'exécution ici serait trompeur).
# =============================================================================

# Journalisation : réutilise le log() de l'appelant s'il en définit un.
if ! declare -f log >/dev/null 2>&1; then
    log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
fi

notifier_verdicts() { # repo self fails warns fail_lines warn_lines
    local repo="${1:-}" self="${2:-}" fails="${3:-0}" warns="${4:-0}"
    local fail_lines="${5:-}" warn_lines="${6:-}"
    local decision sujet corps

    decision=$(verdict_notification "$fails" "$warns")
    [ "$decision" = "silence" ] && return 0

    if [ ! -r "$repo/scripts/lib/lib-alert.sh" ]; then
        echo "[WARN] lib-alert.sh introuvable dans $repo — aucune notification envoyée."
        return 0
    fi

    if [ "$decision" = "critique" ]; then
        # 1 h : à */15, un FAIL persistant ferait 96 e-mails par jour.
        ALERT_COOLDOWN_FILE=/tmp/check-reliability-cooldown
        ALERT_COOLDOWN_SECONDS=3600
        sujet="[5Hostachy] ❌ $fails contrôle(s) de fiabilité en échec sur $self"
        corps=$(printf 'check-reliability.sh sur %s a relevé %s FAIL et %s WARN à %s.\n\nDétail (cette exécution) :\n%s\nLog complet : /var/log/hostachy-reliability.log\n' \
            "$self" "$fails" "$warns" "$(date '+%d/%m/%Y %H:%M')" "$fail_lines")
    else
        # 24 h : un point de vigilance qui dure est une dette, pas une urgence.
        ALERT_COOLDOWN_FILE=/tmp/check-reliability-digest-cooldown
        ALERT_COOLDOWN_SECONDS=86400
        sujet="[5Hostachy] ⚠️ $warns point(s) de vigilance sur $self"
        corps=$(printf 'check-reliability.sh sur %s a relevé %s WARN et aucun FAIL à %s.\n\nAucun ne coupe la production ; laissés sans suite, ils rendent la surveillance aveugle — un rapport de maintenance perdu le 16/08/2026 y a passé deux jours.\n\nDétail (cette exécution) :\n%s\nCe résumé part au plus une fois par 24 h.\nLog complet : /var/log/hostachy-reliability.log\n' \
            "$self" "$warns" "$(date '+%d/%m/%Y %H:%M')" "$warn_lines")
    fi

    ALERT_REPO="$repo"
    # shellcheck source=/dev/null
    source "$repo/scripts/lib/lib-alert.sh"
    alert_if_not_in_cooldown "$sujet" "$corps"
}
