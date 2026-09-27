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

    #  L'écran d'abord : il ne dépend ni du cooldown ni de la configuration SMTP.
    rapporter_verdicts "$@"

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

# ── L'écran d'administration, troisième destinataire (27/09/2026) ────────────
#  Les verdicts de C1 à C30 n'allaient qu'au journal et au courriel : l'écran
#  « Maintenance » ne pouvait montrer ni ce qui était en vigilance, ni si ce
#  contrôleur tournait encore. Ils y sont remontés comme un rapport de tâche
#  (`reliability`), sur le canal des autres scripts (`lib-rapport.sh`).
#
#  ⚠️ PAS à chaque passage : 96 lignes par jour et par nœud dans la table la plus
#  lue de l'écran, dont la rétention est de 20 lignes par tâche — un jour de
#  constats aurait chassé tout le reste. On rend compte quand l'ENSEMBLE des
#  constats change, ou au moins une fois par jour : ce battement est ce qui
#  permet à l'écran de dire « Exécution manquante » d'un contrôleur mort.
#
#  La signature ignore les CHIFFRES : « disque à 61 % » puis « à 62 % » est le
#  même constat, et le compter comme un changement ramènerait un rapport par
#  passage.

#: Au-delà, on renvoie même sans changement. 23 h et non 24 : la synthèse
#: attend un rapport par 24 h (`sante_taches`), et un passage à 23 h 55 raté
#: repousserait le suivant au-delà.
RAPPORT_ECRAN_BATTEMENT_S=82800

#  PURE. $1 signature courante · $2 signature envoyée · $3 âge de l'envoi (s)
#  → envoyer | taire
decision_rapport_ecran() {
    local sig=$1 prec=$2 age=$3
    case "$age" in ''|*[!0-9]*) echo envoyer; return ;; esac
    [ -n "$prec" ] && [ "$sig" = "$prec" ] && [ "$age" -lt "$RAPPORT_ECRAN_BATTEMENT_S" ] \
        && echo taire || echo envoyer
}

#  PURE. Les lignes « [FAIL] … » et « [WARN] … » → un tableau JSON de chaînes.
constats_json() {
    local ligne sortie="" sep=""
    while IFS= read -r ligne; do
        [ -n "$ligne" ] || continue
        sortie="$sortie$sep\"$(rapport_echapper "$ligne")\""
        sep=","
    done <<< "$1"
    printf '[%s]' "$sortie"
}

rapporter_verdicts() { # repo self fails warns fail_lines warn_lines
    local repo="${1:-}" self="${2:-}" fails="${3:-0}" warns="${4:-0}"
    local fail_lines="${5:-}" warn_lines="${6:-}"
    local etat=/var/tmp/hostachy-reliability-rapport sig prec="" prec_t=0
    local statut=succes actif cible="http://localhost" ip cle details maintenant
    command -v rapport_payload >/dev/null 2>&1 \
        || source "$repo/scripts/lib/lib-rapport.sh" 2>/dev/null || return 0

    sig=$(printf '%s%s' "$fail_lines" "$warn_lines" | tr -d '0-9' | md5sum | cut -c1-32)
    [ -r "$etat" ] && read -r prec prec_t < "$etat"
    [ "$(decision_rapport_ecran "$sig" "$prec" "$(( $(date +%s) - ${prec_t:-0} ))")" = envoyer ] \
        || return 0

    [ "$warns" -gt 0 ] && statut=avertissement
    [ "$fails" -gt 0 ] && statut=erreur
    #  Le standby n'a pas d'API : il rend compte à celle de l'ACTIF, comme la
    #  maintenance (`envoyer_rapport`). Pas de table d'adresses ici.
    actif=$(tr -d '[:space:]' < "$repo/.active" 2>/dev/null)
    if [ -n "$actif" ] && [ "$actif" != "$self" ]; then
        ip=$(role_ip "$actif" 2>/dev/null) || ip=""
        [ -n "$ip" ] || { log "  ⚠ Rapport des contrôles non envoyé : IP de l'actif ($actif) inconnue"; return 0; }
        cible="http://$ip"
    fi
    cle=$(rapport_cle "$repo") || { log "  ⚠ Rapport des contrôles non envoyé : MAINTENANCE_KEY absente"; return 0; }

    details=$(printf '{"fail":%d,"warn":%d,"constats":%s}' "$fails" "$warns" \
        "$(constats_json "$fail_lines$warn_lines")")
    maintenant=$(date -u +%Y-%m-%dT%H:%M:%S)
    RAPPORT_HTTP=""
    #  Les FAIL vont AUSSI dans `erreur` : c'est ce que liste « Anomalies
    #  récentes », et un échec critique doit y figurer comme ceux des autres tâches.
    rapport_envoyer "$cible" "$cle" \
        "$(rapport_payload reliability "$self" applicative "$statut" 0 "$details" \
            "$(printf '%s' "$fail_lines" | sed 's/^\[FAIL\] //' | paste -sd'|' - | sed 's/|/ | /g')" \
            "$maintenant" "$maintenant")" \
        "Rapport des contrôles"
    #  Mémorisé seulement s'il a ABOUTI : un envoi perdu se retente au passage
    #  suivant, au lieu d'attendre le battement du lendemain.
    [ "$RAPPORT_HTTP" = "201" ] && printf '%s %s\n' "$sig" "$(date +%s)" > "$etat"
    return 0
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    . "$(dirname "$0")/lib-rapport.sh"
    st=0
    t() { [ "$2" = "$3" ] && echo "PASS  $1 → $3" || { echo "FAIL  $1  attendu=$2 obtenu=$3"; st=1; }; }
    t "premier passage"                   envoyer "$(decision_rapport_ecran a "" 0)"
    t "mêmes constats, 15 min après"      taire   "$(decision_rapport_ecran a a 900)"
    t "constats changés"                  envoyer "$(decision_rapport_ecran b a 900)"
    t "mêmes constats, battement dû"      envoyer "$(decision_rapport_ecran a a 82800)"
    t "âge illisible → on envoie"         envoyer "$(decision_rapport_ecran a a "")"
    t "aucun constat"                     "[]"    "$(constats_json "")"
    t "deux constats, guillemets échappés" \
      '["[WARN] Disque \"rpi1\"","[FAIL] Site KO"]' \
      "$(constats_json $'[WARN] Disque "rpi1"\n[FAIL] Site KO\n')"
    #  La signature ignore les chiffres : 61 % puis 62 % n'est pas un changement.
    s1=$(printf '[WARN] Disque à 61%%' | tr -d '0-9' | md5sum | cut -c1-32)
    s2=$(printf '[WARN] Disque à 62%%' | tr -d '0-9' | md5sum | cut -c1-32)
    t "les chiffres ne font pas un changement" taire "$(decision_rapport_ecran "$s2" "$s1" 900)"
    #  La charge complète est du JSON valide — le 422 du 16/08 venait de là.
    ch=$(rapport_payload reliability rpi1 applicative avertissement 0 \
        "$(printf '{"fail":%d,"warn":%d,"constats":%s}' 0 1 "$(constats_json $'[WARN] l\'actif\tvu')")" "" x x)
    if printf '%s' "$ch" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null \
       || printf '%s' "$ch" | python -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
        echo "PASS  charge utile JSON valide (apostrophe, tabulation)"
    else echo "FAIL  charge utile JSON INVALIDE : $ch"; st=1; fi
    [ "$st" -eq 0 ] && echo "lib-notification : tous les cas passent."
    exit "$st"
fi
