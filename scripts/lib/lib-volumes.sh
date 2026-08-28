#!/bin/bash
# =============================================================================
#  lib-volumes.sh — Installer un contenu dans un volume Docker SANS sudo (#582)
#
#  Module IMPORTÉ, jamais exécuté par un cron : pas de bit x, versionné en 100644.
#
#  ## Le fait
#
#  `bascule.sh` installe trois fois du contenu dans un volume du peer — uploads,
#  état d'authentification WhatsApp, base. La cible est à chaque fois le point de
#  montage d'un volume Docker, que seul root peut écrire. Le geste employé était :
#
#      ssh peer 'sudo rsync -a /tmp/… $(docker volume inspect … )/'
#
#  autorisé par une règle sudo `NOPASSWD: /usr/bin/rsync`.
#
#  🔴 **Cette règle n'est pas scopée, elle en a seulement l'air.** Sans borne de
#  chemin, rsync écrit où il veut — `/etc/sudoers.d/`, `/root/.ssh/authorized_keys`
#  — donc la règle vaut un accès root complet et permanent pour `ptressard`.
#  `standards/03` §8 bis : une permission nommée par l'OUTIL n'est pas une
#  permission bornée ; seul le CHEMIN borne.
#
#  ## Le remède, et ce qu'il n'apporte pas
#
#  Un conteneur jetable ne monte QUE le volume visé. Il n'ouvre **aucun privilège
#  nouveau** : l'appartenance au groupe `docker` est déjà un équivalent root, et
#  elle est antérieure et nécessaire au modèle de déploiement. Ce module ne
#  prétend donc pas supprimer le pouvoir root du compte — il supprime **une
#  seconde voie**, qui restait ouverte sans que rien ne l'utilise pour autre chose
#  que ces trois copies. Prétendre l'inverse serait un faux vert.
#
#  Même canal que `durcir-sudoers.sh`, qui écrit dans `/etc/sudoers.d` ainsi
#  depuis le 27/08/2026, et que la conversion de v2.46.11.
#
#  ## Pourquoi `cp -a` et non `rsync -a`
#
#  Aucune image du parc ne porte rsync, et un `apk add` à chaque bascule ferait
#  dépendre la bascule du réseau — au moment précis où le réseau est ce qu'on
#  vient d'éprouver. `cp -a` couvre exactement `rsync -a` sans `--delete` :
#  récursif, préserve mode, propriétaire, horodatage et liens symboliques.
#
#  Équivalence **vérifiée**, pas supposée — le 28/08/2026 sur le standby, volumes
#  jetables, contre la sortie de `sudo rsync -a` sur la même source : mode,
#  uid:gid, mtime, taille, liens symboliques et noms à espaces identiques,
#  contenus identiques octet à octet.
#
#  ⚠️ `--delete` n'est PAS couvert. La phase 4 (base) en a besoin pour retirer les
#  `app.db-wal` / `app.db-shm` résiduels du peer — c'est la règle d'or
#  anti-corruption, et ce n'est pas la même fonction. Elle s'ajoutera ici quand
#  cette phase-là sera convertie, avec son propre self-test.
#
#  ## Ordre de conversion imposé par #582
#
#  Un appel à la fois, en observant une bascule entre chaque : uploads (fait,
#  28/08/2026), puis authentification WhatsApp, puis la base. La règle sudo ne se
#  retire qu'une fois les trois convertis, et se vérifie par
#  `durcir-sudoers.sh --etat`.
#
#  Test : bash scripts/lib/lib-volumes.sh --selftest
# =============================================================================

# Rend la commande d'installation à exécuter SUR LE PEER, sans l'exécuter.
#
# Fonction PURE : aucune écriture, aucun docker, aucun SSH. C'est ce qui la rend
# éprouvable sans les deux RPi — et ce qui permet au self-test de vérifier la
# FORME du geste, seule chose qu'on puisse contrôler avant 02:00 (les phases de
# bascule écrivent, leur seule preuve est le journal du lendemain).
#
#   $1  nom du volume Docker cible          ex. 5hostachy_uploads
#   $2  répertoire temporaire source        ex. /tmp/sync_uploads
#
# Rend une chaîne vide si un argument manque : l'appelant doit traiter le cas
# comme INCONNU et s'abstenir, jamais construire une commande tronquée —
# `rm -rf ""` et un montage sur `/` sont exactement ce qu'on ne veut pas produire.
cmd_installer_volume() {
    local volume="${1:-}" source="${2:-}"
    [ -n "$volume" ] || return 1
    [ -n "$source" ] || return 1
    #  La source est montée en LECTURE SEULE : le conteneur n'a aucune raison
    #  d'écrire dans /tmp, et le lui interdire est gratuit.
    printf '%s' "docker run --rm -v ${volume}:/dst -v ${source}:/src:ro alpine sh -c \"cp -a /src/. /dst/\" && rm -rf ${source}"
}

# 🔴 `${BASH_SOURCE[0]}` = `$0` : le bloc ne s'exécute QUE si ce fichier est
# lancé directement. Sans ce garde, un script qui fait `source lib-volumes.sh`
# en ayant reçu `--selftest` verrait ses propres tests s'exécuter à sa place.
if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "--selftest" ]; then
    fail=0
    check() { # description attendu obtenu
        if [ "$3" = "$2" ]; then echo "PASS  $1"
        else echo "FAIL  $1"; echo "      attendu : $2"; echo "      obtenu  : $3"; fail=1; fi
    }
    contient() { # description motif
        local cmd; cmd=$(cmd_installer_volume 5hostachy_uploads /tmp/sync_uploads)
        case "$cmd" in *"$2"*) echo "PASS  $1" ;; *) echo "FAIL  $1 — absent : $2"; fail=1 ;; esac
    }
    absent() { # description motif
        local cmd; cmd=$(cmd_installer_volume 5hostachy_uploads /tmp/sync_uploads)
        case "$cmd" in *"$2"*) echo "FAIL  $1 — présent : $2"; fail=1 ;; *) echo "PASS  $1" ;; esac
    }

    echo "== self-test lib-volumes.cmd_installer_volume =="

    #  🔴 LE cas du ticket : c'est la disparition de `sudo` qui EST le correctif.
    #  Un remaniement qui le réintroduirait rouvrirait l'escalade root sans que
    #  rien d'autre ne le dise — le journal de bascule, lui, resterait vert.
    absent   "aucun sudo dans la commande produite"        "sudo"
    absent   "aucun rsync : l'image du parc n'en a pas"    "rsync"
    contient "le volume visé est monté en écriture"        "-v 5hostachy_uploads:/dst"
    #  La source montée en écriture serait un privilège gratuit.
    contient "la source est montée en LECTURE SEULE"       "/tmp/sync_uploads:/src:ro"
    contient "la copie préserve les attributs"             "cp -a /src/. /dst/"
    contient "le temporaire est nettoyé"                   "rm -rf /tmp/sync_uploads"
    #  ⚠️ `cp -a /src/ /dst/` (sans le point) crée `/dst/src` au lieu de copier le
    #  CONTENU. Le volume du peer recevrait un sous-répertoire, les uploads
    #  seraient introuvables, et la bascule n'aurait rien à signaler.
    absent   "pas de copie du répertoire au lieu du contenu" "cp -a /src/ /dst/"

    #  Cas zéro : un argument manquant ne doit pas produire une commande
    #  tronquée. `rm -rf ""` et un montage `-v :/src` sont exactement les deux
    #  gestes qu'une chaîne partielle fabriquerait.
    check "volume absent → aucune commande"  "" "$(cmd_installer_volume ''  /tmp/x || true)"
    check "source absente → aucune commande" "" "$(cmd_installer_volume vol ''     || true)"
    check "les deux absents → aucune commande" "" "$(cmd_installer_volume '' '' || true)"

    #  Le code de retour doit être non nul, sinon un appelant en `set -e` ne
    #  verrait rien et enchaînerait sur la chaîne vide.
    if cmd_installer_volume '' '' >/dev/null 2>&1; then
        echo "FAIL  un argument manquant doit rendre un code d'erreur"; fail=1
    else
        echo "PASS  un argument manquant rend un code d'erreur"
    fi

    #  Le nom du volume et le temporaire ne sont pas codés en dur : les deux
    #  conversions restantes (WhatsApp auth, base) passeront par la même fonction.
    check "la fonction sert un autre volume" \
        "docker run --rm -v 5hostachy_whatsapp_auth:/dst -v /tmp/sync_wa_auth:/src:ro alpine sh -c \"cp -a /src/. /dst/\" && rm -rf /tmp/sync_wa_auth" \
        "$(cmd_installer_volume 5hostachy_whatsapp_auth /tmp/sync_wa_auth)"

    [ $fail -eq 0 ] && echo "== TOUS OK ==" || echo "== ÉCHECS =="
    exit $fail
fi
