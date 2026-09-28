#!/bin/bash
# =============================================================================
#  lib-apt.sh — ce que apt dit des correctifs d'un nœud (C30)
#
#  Trois questions, dans l'ordre où elles se masquent l'une l'autre : la
#  configuration apt est-elle lisible (#1377) ? les listes sont-elles fraîches ?
#  un correctif de sécurité attend-il plus que le régime d'un passage
#  d'`unattended-upgrades` (#1441) ?
#
#  Extrait de `lib-mises-a-jour.sh` le 28/09/2026 : #1441 l'aurait porté au-delà
#  du plafond de 500 lignes. Les MESSAGES de C30 restent là-bas, dans la boucle
#  par nœud que `test_constats_nomment_leur_noeud.py` lit ; ici, la collecte et
#  la décision seulement.
#
#  SOURCÉ (mode 100644) par `lib-mises-a-jour.sh`, qui reprend `COLLECT_APT`
#  dans `COLLECT_MAJ` et appelle `verdict_apt`.
#  Autotest : bash scripts/lib/lib-apt.sh --selftest
# =============================================================================

#: Au-delà, les listes apt sont périmées : `unattended-upgrades` ne voit plus
#: rien, et « aucune mise à jour en attente » ne veut plus rien dire. Le dépôt
#: `*-updates` de Debian est republié presque chaque jour ; sept jours sans
#: listes neuves, c'est une semaine où le nœud n'a rien pu apprendre.
APT_LISTES_MAX_J=${APT_LISTES_MAX_J:-7}

# ── La collecte, exécutée sur CHAQUE nœud (reprise par COLLECT_MAJ) ──────────
#  Même contrainte que `lib-collecte.sh` : chaîne entre guillemets SIMPLES, donc
#  AUCUNE apostrophe en dessous, même en commentaire. Tout ce qui s'explique
#  s'explique ici :
#   - apt_erreurs : lignes `E:` de `apt-config dump` — la configuration est-elle
#     seulement lisible ? (#1377). Vide si apt-config manque : INCONNU.
#   - apt_listes_j : âge en jours de la liste la PLUS RÉCENTE. On mesure la
#     chose (les listes), pas son enregistrement (un tampon de tentative, que
#     `apt-daily` pose même quand il échoue) — `standards/04` §14.
COLLECT_APT='
echo "apt_erreurs=$(command -v apt-config >/dev/null 2>&1 && apt-config dump 2>&1 >/dev/null | grep -c "^E:")"
_t=$(find /var/lib/apt/lists -maxdepth 1 -name "*InRelease" -printf "%T@\n" 2>/dev/null | sort -n | tail -1)
echo "apt_listes_j=$([ -n "$_t" ] && echo $(( ( $(date +%s) - ${_t%.*} ) / 86400 )))"
'

#: Depuis quand chaque correctif de sécurité en attente l'est : « <epoch>
#: <paquet>=<version> » par ligne. Écrit par la collecte LOCALE (root) de chaque
#: nœud, lu aussi par celle du pair (ptressard). Par PAQUET, jamais par
#: ensemble : un nouveau correctif remettrait sinon à zéro l'horloge d'un
#: paquet bloqué, et le masquerait tant qu'il en arrive (#1441).
APT_SECU_VU="${APT_SECU_VU:-/var/lib/hostachy/apt-secu-vu}"
#: Régime : `apt-daily-upgrade.timer` passe chaque jour à 06:00 plus jusqu'à
#: 60 min (RandomizedDelaySec) ; deux passages sont séparés de 25 h au plus. Un
#: correctif publié juste après un passage attend donc jusqu'à 25 h sans aucun
#: défaut. 30 h = ce régime, plus un passage de C30 et un démarrage lent
#: (`standards/04` §18 ; le cas « 24 h 59 » de l'autotest le tient).
APT_SECU_DELAI_S=${APT_SECU_DELAI_S:-108000}

#  La collecte des correctifs de sécurité (paramétrée pour l'autotest).
#  Même contrainte que COLLECT_APT : aucune apostrophe dans la chaîne.
#   - apt_secu : paquets en attente venant d'un dépôt `*-security` ; vide si
#     apt manque (INCONNU) ;
#   - apt_secu_vu_s : depuis combien de secondes le PLUS ANCIEN est en attente ;
#   - apt_passage_s : depuis combien de secondes le dernier passage
#     d'installation (`apt-daily-upgrade`) a DÉMARRÉ — un correctif vu avant ce
#     démarrage a été vu par lui ;
#   - apt_prochain : l'heure du prochain passage, pour le dire.
#  L'ancienneté se relit dans le FICHIER, après son écriture : un relevé qui ne
#  s'écrit pas (disque plein, pair sans droit) rend un âge vide, donc INCONNU —
#  jamais « vu à l'instant » à chaque passage, qui serait un ATTENTE perpétuel.
collecte_secu() {
    printf '%s' '
_f='"$1"'
_n=$(date +%s)
if command -v apt >/dev/null 2>&1; then
_l=$(apt list --upgradable 2>/dev/null | grep -- "-security" | awk -F"[/ ]" "{ print \$1 \"=\" \$3 }" | sort)
echo "apt_secu=$(printf "%s" "$_l" | grep -c .)"
_vu() { awk -v p="$1" "\$2 == p && \$1 ~ /^[0-9]+\$/ { print \$1; exit }" "$_f" 2>/dev/null; }
if [ "$(id -u)" = 0 ] && mkdir -p "$(dirname "$_f")"; then
for _p in $_l; do _e=$(_vu "$_p"); echo "${_e:-$_n} $_p"; done > "$_f.tmp" && mv "$_f.tmp" "$_f"
fi
_v=""
for _p in $_l; do
_e=$(_vu "$_p")
[ -n "$_e" ] && { [ -z "$_v" ] || [ "$_e" -lt "$_v" ]; } && _v=$_e
done
echo "apt_secu_vu_s=${_v:+$(( _n - _v ))}"
else
echo "apt_secu="
fi
_d=$(systemctl show --timestamp=unix -p ExecMainStartTimestamp --value apt-daily-upgrade.service 2>/dev/null)
_a=""; case "$_d" in @[0-9]*) _a=$(( _n - ${_d#@} )) ;; esac
echo "apt_passage_s=$_a"
echo "apt_prochain=$(systemctl show -p NextElapseUSecRealtime --value apt-daily-upgrade.timer 2>/dev/null | awk "{ print substr(\$3, 1, 5) }")"
'
}
COLLECT_APT="$COLLECT_APT$(collecte_secu "$APT_SECU_VU")"

# ── Décision PURE (aucun effet de bord) ──────────────────────────────────────

#  $1 erreurs de configuration · $2 âge des listes (j) · $3 paquets de sécurité
#  $4 depuis combien de secondes le plus ancien attend · $5 depuis combien de
#  secondes le dernier passage d'installation a démarré
#  → OK | ILLISIBLE | PERIMEES | ATTENTE | SECURITE | SANS_PASSAGE | INCONNU
#  L'ordre compte : une configuration illisible rend les listes périmées, et des
#  listes périmées rendent le compte de sécurité faux (il vaut 0 sur rpi2).
#  Annoncer le symptôme le plus profond, c'est dire quoi réparer.
#  Un correctif en attente n'est pas un défaut : il le devient quand un passage
#  l'a vu sans le poser (SECURITE), ou quand il attend au-delà du régime d'un
#  passage (SANS_PASSAGE). Avant, ATTENTE (#1441 : le 28/09/2026, C30 disait
#  « ne les a pas posés » d'un correctif publié quatre heures après le passage).
verdict_apt() {
    local err=$1 age=$2 secu=$3 vu=${4:-} passage=${5:-}
    case "$err" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$err" -gt 0 ] && { echo ILLISIBLE; return; }
    case "$age" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$age" -gt "$APT_LISTES_MAX_J" ] && { echo PERIMEES; return; }
    case "$secu" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    [ "$secu" -gt 0 ] || { echo OK; return; }
    case "$vu" in ''|*[!0-9]*) echo INCONNU; return ;; esac
    case "$passage" in *[!0-9]*) passage='' ;; esac
    if [ -n "$passage" ] && [ "$vu" -gt "$passage" ]; then echo SECURITE
    elif [ "$vu" -gt "$APT_SECU_DELAI_S" ]; then echo SANS_PASSAGE
    elif [ -n "$passage" ]; then echo ATTENTE
    else echo INCONNU; fi
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
    t "apt-config absent → INCONNU, jamais OK"         INCONNU    verdict_apt "" 1 0
    t "âge illisible → INCONNU"                        INCONNU    verdict_apt 0 "" 0
    t "compte de sécurité illisible → INCONNU"         INCONNU    verdict_apt 0 1 ""
    #  #1441 — rpi2 le 28/09 à 17:51 : libheif vu à 12:21, passage à 06:50.
    t "rpi2 le 28/09 : publié après le passage"        ATTENTE    verdict_apt 0 0 3 19800 39660
    t "vu par le passage de ce matin, pas posé"        SECURITE   verdict_apt 0 0 3 36000 7200
    t "vu il y a 31 h, aucun passage depuis"           SANS_PASSAGE verdict_apt 0 0 3 111600 118800
    t "régime : 24 h 59 d'attente reste ATTENTE"       ATTENTE    verdict_apt 0 0 1 89940 90000
    t "passage illisible, attente > délai"             SANS_PASSAGE verdict_apt 0 0 1 111600 ""
    t "passage illisible, attente courte → INCONNU"    INCONNU    verdict_apt 0 0 1 7200 ""
    t "ancienneté illisible → INCONNU, jamais ATTENTE" INCONNU    verdict_apt 0 0 3 "" 7200


    #  #1441 — la collecte des correctifs, sur un apt et un systemd simulés aux
    #  formes RÉELLES (sortie de rpi2 le 28/09/2026).
    tmps=$(mktemp -d); vuf="$tmps/sous/apt-secu-vu"; now=$(date +%s)
    heif='libheif1/stable-security 1.23.4-1~deb13u1 arm64 [upgradable from: 1.19.8-1+deb13u1]'
    apt() { printf 'Listing...\n%s\nbluez/stable 5.82-1.1+rpt2 arm64 [upgradable from: 5.82-1.1+rpt1]\n' "$heif"; }
    systemctl() { case "$*" in
        *ExecMainStartTimestamp*) echo "@$(( now - 36000 ))" ;;
        *NextElapseUSecRealtime*) echo "Tue 2026-09-29 06:39:48 CEST" ;; esac; }
    id() { echo 0; }
    champ() { eval "$(collecte_secu "$vuf")" | sed -n "s/^$1=//p"; }
    t "collecte : seuls les paquets -security comptent" 1 champ apt_secu
    t "collecte : premier relevé → vu à l'instant" oui eval '[ "$(champ apt_secu_vu_s)" -le 5 ] && echo oui'
    t "collecte : relevé écrit, répertoire créé" "libheif1=1.23.4-1~deb13u1" eval 'cut -d" " -f2 "$vuf"'
    t "collecte : début du dernier passage" oui eval 'a=$(champ apt_passage_s); [ "$a" -ge 36000 ] && [ "$a" -le 36005 ] && echo oui'
    t "collecte : heure du prochain passage" 06:39 champ apt_prochain
    #  Un paquet bloqué garde SON ancienneté quand un autre correctif arrive.
    echo "$(( now - 50000 )) libheif1=1.23.4-1~deb13u1" > "$vuf"
    apt() { printf '%s\nlibfoo/stable-security 2.0-1 arm64 [upgradable from: 1.0-1]\n' "$heif"; }
    t "collecte : un nouveau correctif ne remet pas l'horloge à zéro" oui \
      eval '[ "$(champ apt_secu_vu_s)" -ge 50000 ] && echo oui'
    t "collecte : les deux paquets sont relevés" 2 eval 'grep -c . "$vuf"'
    #  Une nouvelle VERSION du même paquet est un nouveau correctif.
    echo "$(( now - 50000 )) libheif1=1.19.9-1" > "$vuf"
    apt() { printf '%s\n' "$heif"; }
    t "collecte : nouvelle version → nouvelle horloge" oui eval '[ "$(champ apt_secu_vu_s)" -le 5 ] && echo oui'
    #  Le pair lit sans écrire : un paquet absent du relevé ne compte pas.
    rm -f "$vuf"; id() { echo 1000; }
    t "collecte : hors root, rien d'écrit ni d'inventé" "" champ apt_secu_vu_s
    t "collecte : hors root, aucun fichier créé" non eval '[ -e "$vuf" ] && echo oui || echo non'
    unset -f apt systemctl id champ; rm -rf "$tmps"

    #  La chaîne assemblée est du shell valide : c'est elle que les nœuds exécutent.
    t "COLLECT_APT assemblé est du shell valide" oui eval 'bash -n <<<"$COLLECT_APT" && echo oui'

    [ "$st" -eq 0 ] && echo "lib-apt : tous les cas passent."
    exit "$st"
fi
