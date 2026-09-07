#!/bin/bash
# =============================================================================
#  lib-parite.sh — Parité de CODE ≠ parité d'IMAGES (#511)
#
#  ## Le fait que ce module rend visible
#
#  Tous les contrôles du projet — le point 10 du pré-check, la série C de
#  check-reliability, la phase 0 de bascule.sh — comparent le `git rev-parse` des
#  deux nœuds. C'est la parité de **code**.
#
#  Or ce n'est pas le code qui sert : ce sont les **images Docker**. Entre les
#  deux il y a un `docker compose build`, et il peut échouer — saturation mémoire
#  pendant le build du front sur un RPi, c'est la cause fréquente.
#
#  🔴 L'état qui en résulte est le plus trompeur du système : parité git VERTE,
#  images périmées. Tous les contrôles disent OK, et un failover sert l'ancienne
#  version. C'est le risque nommé par #448 puis isolé par #511 :
#
#  > « Reste le cas où son build échoue : une alerte part, mais elle *prévient*
#  >   sans *empêcher*. »
#
#  ## Le remède : un fait, pas une déduction
#
#  `auto-deploy.sh` écrit `$REPO/.images-construites` avec le hash du commit
#  **pour lequel le build a réussi** — et ne l'écrit pas quand il échoue. Comparer
#  ce fichier au `git rev-parse HEAD` répond à la seule question qui compte :
#  *« les images que je m'apprête à démarrer correspondent-elles au code que je
#  crois servir ? »*
#
#  ⚠️ Un marqueur absent ne vaut pas « périmé » et ne vaut surtout pas « à
#  jour » : il vaut INCONNU. Un nœud dont le marqueur n'a jamais été écrit — une
#  installation antérieure à ce module — n'a rien prouvé, ni dans un sens ni dans
#  l'autre (`standards/04` §1).
#
#  Test : bash scripts/lib/lib-parite.sh --selftest
# =============================================================================

# ── Fonction PURE — aucun fichier, aucun docker, aucun réseau ────────────────
# Args : hash_git  hash_images
#   hash_git    : `git rev-parse HEAD` du dépôt local (vide si indéterminable)
#   hash_images : contenu de `.images-construites` (vide si absent)
# Échoit : "a-jour" | "images-perimees" | "inconnu"
verdict_parite_servie() {
    local git="${1:-}" images="${2:-}"
    #  Sans l'un OU l'autre, on ne peut RIEN conclure. Répondre « a-jour » ferait
    #  d'un contrôle aveugle un contrôle rassurant, ce qui est pire que pas de
    #  contrôle du tout.
    [ -z "$git" ] && { echo inconnu; return; }
    [ -z "$images" ] && { echo inconnu; return; }
    #  Comparaison sur le PRÉFIXE COMMUN : `git rev-parse HEAD` rend 40
    #  caractères, `--short` en rend 7 à 12 selon la taille du dépôt. Comparer
    #  les chaînes entières rendrait « périmé » un nœud parfaitement à jour, et
    #  ce faux positif ferait désarmer le contrôle en une semaine.
    local n="${#images}"
    [ "$n" -gt "${#git}" ] && n="${#git}"
    [ "$n" -lt 7 ] && { echo inconnu; return; }
    if [ "${git:0:$n}" = "${images:0:$n}" ]; then echo "a-jour"; else echo "images-perimees"; fi
}

# ── Lecture du marqueur (effet de bord : lit un fichier) ─────────────────────
# $1 = racine du dépôt → le hash pour lequel les images ont été construites, ou ""
hash_images_construites() {
    local f="${1:-}/.images-construites"
    [ -r "$f" ] || { echo ""; return; }
    tr -d ' \t\r\n' < "$f"
}

# ── Écriture du marqueur — appelée UNIQUEMENT après un build réussi ──────────
# $1 = racine du dépôt, $2 = hash construit
marquer_images_construites() {
    printf '%s\n' "${2:-}" > "${1:-}/.images-construites" 2>/dev/null || true
}

# ── Self-test (aucun effet de bord) ──────────────────────────────────────────
#
# 🔴 `${BASH_SOURCE[0]}` = `$0` : le bloc ne s'exécute QUE si ce fichier est
# lancé, jamais s'il est sourcé. Sans cette garde, un script qui fait
# `source lib-parite.sh` en ayant reçu `--selftest` verrait ses propres
# positionnels hérités ici, exécuterait CE self-test et sortirait — sa propre
# batterie ne tournerait jamais, et la CI serait verte en mesurant autre chose.
#
# Constaté en écrivant #511 : `health-watch.sh --selftest` s'est mis à afficher
# les huit cas de la parité au lieu de ses cinq cas de `decide_failover`. C'est
# aussi pourquoi `lib-role.sh` est sourcé APRÈS le bloc de self-test de ses
# appelants — un contournement, là où la garde est le remède.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    check() { # description attendu git images
        local desc="$1" exp="$2"; shift 2
        local got; got=$(verdict_parite_servie "$@")
        if [ "$got" = "$exp" ]; then echo "PASS  $desc  → $got"
        else echo "FAIL  $desc  attendu=$exp obtenu=$got"; fail=1; fi
    }
    LONG=a1b2c3d4e5f60718293a4b5c6d7e8f9012345678
    AUTRE=9876543210fedcba9876543210fedcba98765432

    echo "== self-test lib-parite.verdict_parite_servie =="
    check "images construites sur le commit courant"     "a-jour"          "$LONG" "$LONG"
    check "marqueur court (git --short) mais concordant" "a-jour"          "$LONG" "a1b2c3d"
    check "build échoué : images restées en arrière"     "images-perimees" "$LONG" "$AUTRE"
    check "marqueur court divergent"                     "images-perimees" "$LONG" "9876543"
    # 🔴 Les trois cas qui doivent rendre INCONNU, jamais OK.
    check "marqueur absent (nœud jamais construit)"      "inconnu"         "$LONG" ""
    check "git indéterminable (dépôt illisible)"         "inconnu"         ""      "$LONG"
    check "les deux indéterminables"                     "inconnu"         ""      ""
    #  Un marqueur tronqué ne prouve rien : deux commits partagent facilement
    #  quatre caractères. En dessous de sept, on refuse de conclure plutôt que de
    #  déclarer une parité sur une coïncidence.
    check "marqueur trop court pour trancher"            "inconnu"         "$LONG" "a1b2"
    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
