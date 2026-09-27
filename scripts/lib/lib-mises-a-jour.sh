#!/bin/bash
# =============================================================================
#  lib-mises-a-jour.sh — ce qui se met à jour HORS des dépendances applicatives
#
#  Les dépendances Python et npm ont leur veille (Dependabot, pip-audit, npm
#  audit). Deux couches n'en avaient AUCUNE (audit du 27/09/2026) :
#
#  1. le SYSTÈME des deux RPi (#1378). Le fichier `20auto-upgrades` de rpi2 était
#     mal formé depuis le 18/04/2026 : `apt-daily` échouait chaque jour, systemd
#     le comptait comme réussi, et `apt list --upgradable` rendait 0 — sur des
#     listes vieilles de cinq mois (#1377). Cinq mois sans correctif de
#     sécurité, et vingt-neuf contrôles au vert à chaque quart d'heure ;
#  2. les IMAGES DE BASE des conteneurs (#1379). `docker compose build` ne
#     re-télécharge jamais une image déjà présente, et Dependabot ne change que
#     l'étiquette : les correctifs publiés sous `python:3.12-slim` n'entraient
#     dans aucun conteneur.
#
#  Ce module porte les deux, parce qu'ils répondent à la même question — « ce
#  nœud reçoit-il ses correctifs ? » — et qu'aucun des deux n'a d'autre maison.
#
#  Il est SOURCÉ (mode 100644) par `lib-collecte.sh` (le snippet `COLLECT_MAJ`),
#  `lib-conformite.sh` (les verdicts de C30) et `maintenance.sh` (les images).
#  Autotest : bash scripts/lib/lib-mises-a-jour.sh --selftest
# =============================================================================

#: Au-delà, les listes apt sont périmées : `unattended-upgrades` ne voit plus
#: rien, et « aucune mise à jour en attente » ne veut plus rien dire. Le dépôt
#: `*-updates` de Debian est republié presque chaque jour ; sept jours sans
#: listes neuves, c'est une semaine où le nœud n'a rien pu apprendre.
APT_LISTES_MAX_J=${APT_LISTES_MAX_J:-7}

# ── La collecte, exécutée sur CHAQUE nœud (ajoutée à COLLECT) ────────────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe en dessous, même en commentaire. Tout ce qui s'explique
#  s'explique ici :
#   - apt_erreurs : lignes `E:` de `apt-config dump` — la configuration est-elle
#     seulement lisible ? (#1377). Vide si apt-config manque : INCONNU.
#   - apt_listes_j : âge en jours de la liste la PLUS RÉCENTE. On mesure la
#     chose (les listes), pas son enregistrement (un tampon de tentative, que
#     `apt-daily` pose même quand il échoue) — `standards/04` §14.
#   - apt_secu : paquets en attente venant d un dépôt `*-security`.
#   - noyau_actif / noyau_installe : le noyau qui tourne, et le plus récent
#     installé de la MÊME saveur (`+rpt-rpi-2712`) — lu dans /lib/modules, donc
#     sans dépendre du nom du paquet, qui change d une image Raspberry à l autre.
COLLECT_MAJ='
echo "apt_erreurs=$(command -v apt-config >/dev/null 2>&1 && apt-config dump 2>&1 >/dev/null | grep -c "^E:")"
_t=$(find /var/lib/apt/lists -maxdepth 1 -name "*InRelease" -printf "%T@\n" 2>/dev/null | sort -n | tail -1)
echo "apt_listes_j=$([ -n "$_t" ] && echo $(( ( $(date +%s) - ${_t%.*} ) / 86400 )))"
echo "apt_secu=$(command -v apt >/dev/null 2>&1 && apt list --upgradable 2>/dev/null | grep -c -- "-security")"
_k=$(uname -r)
echo "noyau_actif=$_k"
echo "noyau_installe=$(ls -1 /lib/modules 2>/dev/null | grep -F -- "+${_k#*+}" | sort -V | tail -1)"
'

# ── Décisions PURES (aucun effet de bord) ────────────────────────────────────

#  $1 erreurs de configuration · $2 âge des listes (j) · $3 paquets de sécurité
#  → OK | ILLISIBLE | PERIMEES | SECURITE | INCONNU
#  L'ordre compte : une configuration illisible rend les listes périmées, et des
#  listes périmées rendent le compte de sécurité faux (il vaut 0 sur rpi2).
#  Annoncer le symptôme le plus profond, c'est dire quoi réparer.
verdict_apt() {
    local err=$1 age=$2 secu=$3
    case "$err" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$err" -gt 0 ] && { echo ILLISIBLE; return; }
    case "$age" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$age" -gt "$APT_LISTES_MAX_J" ] && { echo PERIMEES; return; }
    case "$secu" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$secu" -gt 0 ] && { echo SECURITE; return; }
    echo OK
}

#  $1 noyau qui tourne · $2 plus récent installé de la même saveur
#  → OK | REDEMARRAGE | INCONNU
#  `unattended-upgrades` installe, il ne redémarre pas : un noyau corrigé qui
#  attend un redémarrage ne protège de rien.
verdict_noyau() {
    local actif=$1 installe=$2
    [ -n "$actif" ] && [ -n "$installe" ] || { echo INCONNU; return; }
    [ "$actif" = "$installe" ] && echo OK || echo REDEMARRAGE
}

#  $1 et $2 : les noyaux qui tournent sur les deux nœuds → OK | DIVERGENCE | INCONNU
#  Deux nœuds qui se relaient chaque nuit doivent se comporter pareil ; le
#  27/09/2026, rpi1 tournait en 6.12.62 et rpi2 en 6.12.75.
verdict_noyaux_parite() {
    [ -n "$1" ] && [ -n "$2" ] || { echo INCONNU; return; }
    [ "${1%%+*}" = "${2%%+*}" ] && echo OK || echo DIVERGENCE
}

#  Les images de base nommées par des Dockerfile, une par ligne, sans doublon.
#  Un `FROM` qui désigne une ÉTAPE du même fichier (`FROM builder`) n'est pas une
#  image à télécharger, ni `scratch`. Lues dans les fichiers, jamais recopiées :
#  une liste tenue à la main oublierait la prochaine image.
images_de_base() {
    #  `sub(/\r$/…)` : deux Dockerfile du dépôt sont en CRLF, et l'awk des RPi
    #  garde le `\r` (celui de Git Bash le retire : sur le poste, rien ne se voit).
    awk '
        { sub(/\r$/, "") }
        FNR == 1 { delete etapes }
        toupper($1) == "FROM" {
            i = 2
            while ($i ~ /^--/) i++
            img = $i
            if (img != "" && img != "scratch" && !(img in etapes)) print img
            if (toupper($(i + 1)) == "AS") etapes[$(i + 2)] = 1
        }
    ' "$@" 2>/dev/null | sort -u
}

# ── Les verdicts de C30, émis par check-reliability (via lib-conformite) ─────
#  Dépend de l'appelant : ok/warn, SELF/PEER/PEER_OK et les champs S_*/P_*.
#  Tout sort en WARN, donc au digest quotidien : aucune de ces situations
#  n'arrête le site, et un redémarrage reste un geste manuel, le standby
#  d'abord. Un FAIL à */15 serait une alerte par heure qu'on apprendrait à
#  ignorer.
mises_a_jour_verdicts() {
    local n p v
    for n in "$SELF" "$PEER"; do
        if [ "$n" = "$SELF" ]; then p=S; else [ "$PEER_OK" -eq 0 ] || continue; p=P; fi
        local err age secu actif inst
        eval "err=\${${p}_apt_erreurs:-} age=\${${p}_apt_listes_j:-} secu=\${${p}_apt_secu:-}"
        eval "actif=\${${p}_noyau_actif:-} inst=\${${p}_noyau_installe:-}"
        v=$(verdict_apt "$err" "$age" "$secu")
        case "$v" in
            OK)        ok   "Mises à jour système sur $n : listes apt de ${age} j, aucun correctif de sécurité en attente" ;;
            ILLISIBLE) warn "Configuration apt ILLISIBLE sur $n ($err erreur(s)) — apt-daily échoue chaque jour en silence, AUCUNE mise à jour n'arrive (#1377) : 'apt-config dump' pour voir la ligne fautive" ;;
            PERIMEES)  warn "Listes apt périmées sur $n : ${age} j (seuil ${APT_LISTES_MAX_J} j) — le nœud ne voit plus les correctifs ; vérifier 'systemctl status apt-daily' et /etc/apt/apt.conf.d/20auto-upgrades" ;;
            SECURITE)  warn "$secu correctif(s) de sécurité en attente sur $n — unattended-upgrades ne les a pas posés : 'sudo unattended-upgrade -v'" ;;
            *)         warn "Mises à jour système INCONNUES sur $n (erreurs='${err:-vide}' âge='${age:-vide}' sécurité='${secu:-vide}') — ni vert ni rouge" ;;
        esac
        case "$(verdict_noyau "$actif" "$inst")" in
            OK)          ok   "Noyau de $n à jour ($actif)" ;;
            REDEMARRAGE) warn "Redémarrage requis sur $n : tourne en $actif, $inst est installé — redémarrer le STANDBY d'abord, l'actif après une bascule" ;;
            *)           warn "Noyau de $n INCONNU (tourne='${actif:-vide}' installé='${inst:-vide}') — ni vert ni rouge" ;;
        esac
    done
    [ "$PEER_OK" -eq 0 ] || return 0
    case "$(verdict_noyaux_parite "${S_noyau_actif:-}" "${P_noyau_actif:-}")" in
        OK)         ok   "Même noyau sur les 2 nœuds (${S_noyau_actif%%+*})" ;;
        DIVERGENCE) warn "Noyaux DIVERGENTS — $SELF en ${S_noyau_actif%%+*}, $PEER en ${P_noyau_actif%%+*} : les deux nœuds se relaient chaque nuit et ne se comportent pas pareil. Le dépôt archive.raspberrypi.com n'est pas dans les origines d'unattended-upgrades : le noyau ne se met à jour qu'à la main" ;;
        *)          warn "Parité des noyaux INCONNUE ($SELF='${S_noyau_actif:-vide}' $PEER='${P_noyau_actif:-vide}')" ;;
    esac
}

# ── Auto-test (job CI `test-scripts`) ─────────────────────────────────────────
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    st=0
    t() { local r; r=$("${@:3}"); [ "$r" = "$2" ] && echo "PASS  $1 → $r" || { echo "FAIL  $1  attendu=$2 obtenu=$r"; st=1; }; }

    t "nœud sain"                                      OK         verdict_apt 0 1 0
    t "rpi2 le 27/09 : configuration illisible"        ILLISIBLE  verdict_apt 1 162 0
    t "illisible l'emporte sur périmé"                 ILLISIBLE  verdict_apt 2 0 5
    t "listes vieilles de 8 j"                         PERIMEES   verdict_apt 0 8 0
    t "listes à 7 j : encore bon"                      OK         verdict_apt 0 7 0
    t "périmé l'emporte sur « 0 correctif »"           PERIMEES   verdict_apt 0 162 0
    t "correctifs de sécurité en attente"              SECURITE   verdict_apt 0 1 3
    t "apt-config absent → INCONNU, jamais OK"         INCONNU    verdict_apt "" 1 0
    t "âge illisible → INCONNU"                        INCONNU    verdict_apt 0 "" 0
    t "compte de sécurité illisible → INCONNU"         INCONNU    verdict_apt 0 1 ""

    t "noyau à jour"            OK          verdict_noyau 6.12.75+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "noyau en attente"        REDEMARRAGE verdict_noyau 6.12.62+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "rien d'installé lu"      INCONNU     verdict_noyau 6.12.62+rpt-rpi-2712 ""

    t "noyaux identiques"       OK          verdict_noyaux_parite 6.12.75+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "rpi1 / rpi2 le 27/09"    DIVERGENCE  verdict_noyaux_parite 6.12.62+rpt-rpi-2712 6.12.75+rpt-rpi-2712
    t "peer muet"               INCONNU     verdict_noyaux_parite 6.12.62+rpt-rpi-2712 ""

    tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
    printf 'FROM node:22-alpine AS builder\nRUN x\nFROM node:22-alpine AS runner\nCOPY --from=builder /a /b\n' > "$tmp/front"
    printf 'FROM python:3.12-slim\n' > "$tmp/api"
    printf 'FROM --platform=linux/arm64 caddy:2 AS base\nFROM base\nFROM scratch\n' > "$tmp/caddy"
    t "étapes, doublons, --platform et scratch écartés" \
      "caddy:2 node:22-alpine python:3.12-slim" \
      eval 'images_de_base "$tmp/front" "$tmp/api" "$tmp/caddy" | paste -sd" " -'
    #  Une étape d'un fichier ne masque pas une image du même nom dans un autre.
    printf 'FROM alpine AS python\n' > "$tmp/a"; printf 'FROM python\n' > "$tmp/b"
    t "une étape ne déborde pas sur le fichier suivant" "alpine python" \
      eval 'images_de_base "$tmp/a" "$tmp/b" | paste -sd" " -'
    t "aucun fichier → rien"    ""  images_de_base "$tmp/absent"
    #  🔴 Vécu sur le banc du 27/09/2026 : deux Dockerfile du dépôt sont en CRLF,
    #  le `\r` restait collé au nom, et `docker pull` répondait « invalid
    #  reference format » — deux images sur quatre jamais tirées.
    printf 'FROM python:3.12-slim\r\nRUN x\r\n' > "$tmp/crlf"
    t "Dockerfile en CRLF : nom sans retour chariot (\\r rendu en #)" "python:3.12-slim" \
      eval 'images_de_base "$tmp/crlf" | tr "\r" "#"'

    #  La collecte est du shell VALIDE une fois assemblée (même piège que COLLECT).
    if bash -n <(printf '%s' "$COLLECT_MAJ") 2>/dev/null; then echo "PASS  COLLECT_MAJ est du shell valide"
    else echo "FAIL  COLLECT_MAJ est du shell INVALIDE (apostrophe dans la chaîne ?)"; st=1; fi

    [ "$st" -eq 0 ] && echo "lib-mises-a-jour : tous les cas passent."
    exit "$st"
fi
