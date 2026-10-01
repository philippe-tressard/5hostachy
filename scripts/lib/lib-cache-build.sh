#!/bin/bash
# =============================================================================
#  lib-cache-build.sh — Borner le cache de build Docker, et DIRE ce qu'on a
#  mesuré (#1524, 01/10/2026)
#
#  Module SOURCÉ par `auto-deploy.sh` (après chaque construction) et par
#  `maintenance.sh` (chaque dimanche) : la seule écriture de la purge, de son
#  plafond et de ses âges. Pas de bit x (`lib-*.sh` sont en 100644).
#
#  ## Ce qui ne marchait pas
#
#  Le 01/10/2026, rpi1 portait 40 Go de cache — et `auto-deploy` écrivait toutes
#  les cinq minutes « Cache de build ramené sous 10 Go. ». Une purge complète a
#  libéré 37 Go RÉELS (disque de 50 à 13 Go). Mesuré sur le nœud, Docker 29 avec
#  le stockage d'images containerd (`io.containerd.snapshotter.v1`) :
#
#  | Commande                                   | Ce qu'elle retire                    |
#  |--------------------------------------------|--------------------------------------|
#  | `prune --keep-storage` / `--max-used-space`| la seule part « récupérable »        |
#  | `prune --filter until=…` SANS `-a`         | idem                                 |
#  | `prune -a --filter until=…`                | aussi la part PARTAGÉE avec les images |
#
#  La part partagée — des instantanés communs au cache et aux images, que
#  `docker system df` ne compte pas comme récupérables — était de 30 Go sur 40.
#  Aucune des deux purges n'avait `-a` : elles n'y ont jamais touché, et le
#  plafond se calcule sur ce qu'elles voient, pas sur le disque.
#
#  ## Le remède
#
#  1. `-a` sur les deux passes. Par ÂGE d'abord : `until` porte sur la DERNIÈRE
#     UTILISATION d'une entrée, et le build qui vient de finir a touché tout ce
#     qu'il a réutilisé — après une construction, une fenêtre courte n'évince
#     donc que ce que plus rien n'emploie. Le prochain build reste rapide, et
#     `npm run build` n'est pas rejoué (risque d'OOM sur le RPi).
#  2. Le plafond ensuite, en garde-fou de la part récupérable.
#  3. La taille est MESURÉE avant et après, et c'est elle qu'on écrit. L'ancienne
#     ligne était posée sur le code de retour de docker : elle annonçait un
#     résultat qu'elle n'avait pas regardé (`standards/04`, observer la chose).
#
#  ⚠️ Le cache BuildKit est commun au daemon : rpi2 y porte aussi List-dons, et
#  `builder prune` n'a aucun filtre par projet. Ses couches inutilisées depuis
#  plus de `BUILD_CACHE_APRES_BUILD_H` partent avec les nôtres — son prochain
#  build est plus lent, jamais faux.
#
#  Test : bash scripts/lib/lib-cache-build.sh --selftest
# =============================================================================

#  `cache_go` (« 64.68GB » → 64) vit dans lib-verdicts.sh, qui le prête aussi à C16.
#  shellcheck source=lib-verdicts.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib-verdicts.sh"

#  Plafond de la part récupérable : les couches les plus récemment employées
#  sont gardées. Ne pas descendre trop bas — la bascule nocturne reconstruit
#  l'image du peer et compte sur ce cache.
BUILD_CACHE_KEEP=10737418240        # 10 Go
BUILD_CACHE_MAX_AGE_H=168           # dimanche : 7 j, périmé pour tous les projets
BUILD_CACHE_APRES_BUILD_H=24        # après un build : ce que celui-ci n'a pas réutilisé

# ── La taille brute, telle que `docker system df` la rend (« 1.369GB ») ──────
#  Vide si docker ne répond pas : le bilan le dira INCONNU, jamais OK.
cache_build_taille() {
    docker system df --format "{{.Type}}|{{.Size}}" 2>/dev/null \
        | grep -i "^Build Cache" | cut -d"|" -f2 | tr -d " " || true
}

# ── Le bilan d'une purge (PURE — testable) ───────────────────────────────────
#  $1 avant · $2 après · $3 âge (h) · $4 passes refusées par docker (vide si aucune)
#  Une ligne, préfixée de « ⚠ » dès que la purge n'a pas prouvé son effet.
cache_build_bilan() {
    local avant="$1" apres="$2" age="$3" refus="${4:-}" plafond_go go
    #  `docker system df` parle en Go DÉCIMAUX, le plafond est en octets (10 Gio,
    #  soit 10,74 Go) : comparés en Gio, 10,43 Go passaient pour un dépassement.
    #  `cache_go` tronque, d'où la comparaison stricte : on alerte dès 11 Go.
    plafond_go=$(( BUILD_CACHE_KEEP / 1000000000 ))
    go=$(cache_go "$apres")
    if [ "$go" -lt 0 ]; then
        echo "⚠ Cache de build : taille illisible après purge (avant : ${avant:-?}) — effet INCONNU."
    elif [ -n "$refus" ]; then
        echo "⚠ Cache de build : purge $refus refusée par docker — ${avant:-?} → $apres."
    elif [ "$go" -gt "$plafond_go" ]; then
        echo "⚠ Cache de build : ${avant:-?} → $apres, toujours au-dessus du plafond de ${plafond_go} Go."
    else
        echo "Cache de build : ${avant:-?} → $apres (inutilisé depuis plus de ${age} h retiré, plafond ${plafond_go} Go)."
    fi
}

# ── La purge : par âge, puis au plafond, toutes deux avec `-a` ───────────────
#  $1 = âge maximal en heures. Écrit le bilan mesuré sur la sortie standard.
cache_build_borner() {
    local age="$1" avant apres refus=""
    avant=$(cache_build_taille)
    docker builder prune -af --filter "until=${age}h" >/dev/null 2>&1 \
        || refus="par âge"
    docker builder prune -af --max-used-space "$BUILD_CACHE_KEEP" >/dev/null 2>&1 \
        || refus="${refus:+$refus et }au plafond"
    apres=$(cache_build_taille)
    cache_build_bilan "$avant" "$apres" "$age" "$refus"
}

# ── Self-test ────────────────────────────────────────────────────────────────
#  Gardé par BASH_SOURCE : un script qui SOURCE ce module en ayant reçu
#  `--selftest` ne doit pas exécuter celui-ci (`lib-parite.sh`, #511).
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    attendu() {  # $1 libellé · $2 motif attendu · $3… arguments du bilan
        local lib="$1" motif="$2" got; shift 2
        got=$(cache_build_bilan "$@")
        if printf '%s' "$got" | grep -qE "$motif"; then
            echo "PASS  $lib"
        else
            echo "FAIL  $lib — « $got »"; fail=1
        fi
    }
    echo "== self-test : bilan de la purge du cache de build =="
    attendu "sous le plafond → bilan sans alerte"      '^Cache de build : 40.02GB → 1.2GB'  40.02GB 1.2GB 24 ""
    attendu "sous le gigaoctet → bilan sans alerte"   '^Cache de build : '                  2GB 980MB 24 ""
    #  Le cas du 01/10/2026 : docker répond 0, rien ne bouge. L'ancienne ligne
    #  disait « ramené sous 10 Go » ; celle-ci doit le refuser.
    attendu "purge sans effet au-dessus du plafond"   '^⚠ .*toujours au-dessus'             40.02GB 40.02GB 24 ""
    #  rpi2, 01/10/2026 : 10,43 Go, sous les 10 Gio du plafond. Comparé en Gio,
    #  le bilan criait au dépassement — sur un cache tout entier servi la veille.
    attendu "10,43 Go sous un plafond de 10 Gio → sans alerte" '^Cache de build : '           11.31GB 10.43GB 24 ""
    attendu "11 Go → alerte"                          '^⚠ .*toujours au-dessus'             12GB 11.2GB 24 ""
    attendu "taille illisible → INCONNU, jamais OK"   '^⚠ .*INCONNU'                        40GB "" 24 ""
    attendu "passe refusée par docker → dite"         '^⚠ .*par âge refusée'                3GB 2GB 24 "par âge"
    attendu "avant illisible, après mesuré → ?"       '^Cache de build : \? → '             "" 1GB 168 ""

    echo "== self-test : la purge garde -a sur ses deux passes =="
    #  Sans `-a`, la part partagée avec les images n'est jamais retirée : c'est
    #  le défaut de #1524. On lit la fonction elle-même, pas une copie.
    corps=$(declare -f cache_build_borner)
    n_prune=$(printf '%s\n' "$corps" | grep -c 'builder prune' || true)
    n_tout=$(printf '%s\n' "$corps" | grep -cE 'builder prune -a|builder prune [^|]*--all' || true)
    if [ "$n_prune" -ge 2 ] && [ "$n_prune" -eq "$n_tout" ]; then
        echo "PASS  ${n_prune} passes, toutes avec -a"
    else
        echo "FAIL  ${n_tout} passe(s) avec -a sur ${n_prune}"; fail=1
    fi

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
